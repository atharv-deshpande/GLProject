import logging, re
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.chat import ChatMessage
from app.models.document import Document, DocumentChunk
from app.models.user import User, Role
from app.schemas.knowledge import ChatResponse, Citation, KnowledgeQuery, SearchHit, SearchResponse
from app.modules.embeddings.ollama_embeddings import EmbeddingServiceError, OllamaEmbeddingService
from app.modules.rag.answer_service import GenerationError, OllamaAnswerService
from app.modules.retrieval.authorization import authorized_department_ids
from app.modules.retrieval.qdrant_store import QdrantVectorStore, VectorStoreError
logger=logging.getLogger(__name__)
router=APIRouter(tags=["Knowledge"])

def validate_citation_markers(answer:str,sources:list[dict])->tuple[str,set[str]]:
    allowed={s["source_id"] for s in sources}; cited=set()
    def replace(m):
        sid=m.group(1)
        if sid not in allowed:return f"[unverified citation {sid}]"
        cited.add(sid); return m.group(0)
    return re.sub(r"\[(S[0-9]+)\]",replace,answer),cited

def retrieve_authorized(payload:KnowledgeQuery,db:Session,user:User)->list[dict]:
    dept_ids=authorized_department_ids(db,user,payload.department_id)
    if not dept_ids:return []
    try:
        vector=OllamaEmbeddingService().embed_query(payload.query)
        candidates=QdrantVectorStore().search(vector,dept_ids,payload.top_k or settings.RAG_TOP_K)
    except (EmbeddingServiceError,VectorStoreError) as exc:
        logger.exception("Knowledge retrieval failed")
        raise HTTPException(status_code=503,detail="Knowledge retrieval is temporarily unavailable.") from exc
    ids=[]
    for item in candidates:
        try:ids.append(UUID(str(item["chunk_id"])))
        except (ValueError,TypeError,KeyError):logger.warning("Ignoring invalid Qdrant chunk ID.")
    rows=db.execute(select(DocumentChunk,Document).join(Document,Document.id==DocumentChunk.document_id)
        .where(DocumentChunk.id.in_(ids),Document.department_id.in_(dept_ids))).all() if ids else []
    row_map={c.id:(c,d) for c,d in rows}; hits=[]
    for item in candidates:
        try:cid=UUID(str(item["chunk_id"]))
        except (ValueError,TypeError,KeyError):continue
        pair=row_map.get(cid)
        if not pair:continue
        c,d=pair; score=float(item.get("score",0))
        if score<settings.RAG_MIN_SCORE:continue
        hits.append({"chunk_id":c.id,"document_id":d.id,"document_name":d.original_filename,
            "department_id":d.department_id,"page_number":c.page_number,"section_title":c.section_title,
            "content":c.content,"score":score})
    return hits

@router.post("/api/v1/search",response_model=SearchResponse)
def search_knowledge(payload:KnowledgeQuery,current_user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    hits=retrieve_authorized(payload,db,current_user)
    return SearchResponse(query=payload.query,results=[SearchHit(**h) for h in hits],total=len(hits))

@router.post("/api/v1/chat",response_model=ChatResponse)
def chat_knowledge(payload:KnowledgeQuery,current_user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    hits=retrieve_authorized(payload,db,current_user)
    if not hits:
        answer="I could not find sufficiently relevant information in the documents you are authorized to access."
        db.add(ChatMessage(user_id=current_user.id,prompt=payload.query,answer=answer)); db.commit()
        return ChatResponse(query=payload.query,answer=answer,citations=[],insufficient_evidence=True)
    sources=[{"source_id":f"S{i}","document_name":h["document_name"],"page_number":h["page_number"],
        "section_title":h["section_title"],"content":h["content"]} for i,h in enumerate(hits,1)]
    try:
        generated=OllamaAnswerService().answer(payload.query,sources)
        answer,cited=validate_citation_markers(generated["answer"],sources)
    except GenerationError as exc:
        logger.exception("Answer generation failed")
        raise HTTPException(status_code=503,detail="Answer generation is temporarily unavailable.") from exc
    citations=[Citation(source_id=s["source_id"],document_id=h["document_id"],document_name=h["document_name"],
        page_number=h["page_number"],section_title=h["section_title"],chunk_id=h["chunk_id"])
        for s,h in zip(sources,hits) if s["source_id"] in cited]
    db.add(ChatMessage(user_id=current_user.id,prompt=payload.query,answer=answer,
        input_tokens=generated["input_tokens"],output_tokens=generated["output_tokens"],duration_ms=generated["duration_ms"]))
    db.commit()
    return ChatResponse(query=payload.query,answer=answer,citations=citations,insufficient_evidence=False)

@router.get("/api/v1/chat/history")
def chat_history(current_user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    is_admin=getattr(current_user.role,"value",current_user.role)==Role.ADMIN.value
    query=select(ChatMessage,User.email).join(User,User.id==ChatMessage.user_id).order_by(ChatMessage.created_at.desc())
    if not is_admin:query=query.where(ChatMessage.user_id==current_user.id).limit(5)
    rows=db.execute(query).all()
    return [{"id":str(m.id),"user_id":str(m.user_id),"email":email,"prompt":m.prompt,"answer":m.answer,
        "input_tokens":m.input_tokens,"output_tokens":m.output_tokens,"duration_ms":m.duration_ms,
        "created_at":m.created_at.isoformat()} for m,email in rows]

@router.get("/api/v1/chat/usage")
def chat_usage(current_user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    is_admin=getattr(current_user.role,"value",current_user.role)==Role.ADMIN.value
    if is_admin:
        rows=db.execute(select(User.id,User.email,func.coalesce(func.sum(ChatMessage.input_tokens),0),
            func.coalesce(func.sum(ChatMessage.output_tokens),0),func.count(ChatMessage.id),
            func.coalesce(func.sum(ChatMessage.duration_ms),0)).outerjoin(ChatMessage,ChatMessage.user_id==User.id)
            .group_by(User.id,User.email).order_by(User.email)).all()
        return {"users":[{"user_id":str(r[0]),"email":r[1],"input_tokens":int(r[2]),"output_tokens":int(r[3]),
            "chat_sessions":int(r[4]),"usage_time_ms":int(r[5])} for r in rows],
            "total_input_tokens":sum(int(r[2]) for r in rows),"total_output_tokens":sum(int(r[3]) for r in rows)}
    r=db.execute(select(func.coalesce(func.sum(ChatMessage.input_tokens),0),
        func.coalesce(func.sum(ChatMessage.output_tokens),0),func.count(ChatMessage.id),
        func.coalesce(func.sum(ChatMessage.duration_ms),0)).where(ChatMessage.user_id==current_user.id)).one()
    return {"input_tokens":int(r[0]),"output_tokens":int(r[1]),"chat_sessions":int(r[2]),"usage_time_ms":int(r[3])}
