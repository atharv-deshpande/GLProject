from uuid import UUID
from pydantic import BaseModel,EmailStr,Field,field_validator
from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy import func,select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import Department,Role,User,UserDepartment
from app.modules.auth.password import hash_password
from app.schemas.auth import UserResponse
router=APIRouter(prefix="/users",tags=["Users"])

def require_admin(current_user:User=Depends(get_current_user))->User:
    if getattr(current_user.role,"value",current_user.role)!=Role.ADMIN.value:
        raise HTTPException(status_code=403,detail="Administrator access required.")
    return current_user

class UserCreate(BaseModel):
    email:EmailStr
    password:str=Field(min_length=8,max_length=128)
    role:Role=Role.USER
    department_ids:list[UUID]=Field(default_factory=list)
    @field_validator("email")
    @classmethod
    def company_email(cls,value:EmailStr):
        value=str(value).strip().lower()
        if not value.endswith("@abcerp.com"):raise ValueError("Email must end with @abcerp.com.")
        return value

class UserAdminResponse(BaseModel):
    id:UUID
    email:EmailStr
    role:str
    is_active:bool
    department_ids:list[UUID]
class UserUpdate(BaseModel):
    role:Role|None=None
    is_active:bool|None=None
    department_ids:list[UUID]|None=None

@router.get("/me",response_model=UserResponse)
def me(current_user:User=Depends(get_current_user)):
    return UserResponse(id=str(current_user.id),email=current_user.email,role=current_user.role.value,is_active=current_user.is_active)

@router.get("",response_model=list[UserAdminResponse])
def list_users(_:User=Depends(require_admin),db:Session=Depends(get_db)):
    users=db.scalars(select(User).order_by(User.email)).all()
    return [UserAdminResponse(id=u.id,email=u.email,role=u.role.value,is_active=u.is_active,
        department_ids=list(db.scalars(select(UserDepartment.department_id).where(UserDepartment.user_id==u.id)).all())) for u in users]

@router.post("",response_model=UserAdminResponse,status_code=status.HTTP_201_CREATED)
def create_user(payload:UserCreate,_:User=Depends(require_admin),db:Session=Depends(get_db)):
    email=str(payload.email).strip().lower()
    if db.scalar(select(User.id).where(func.lower(User.email)==email)):
        raise HTTPException(status_code=409,detail="A user with this email already exists.")
    depts=db.scalars(select(Department).where(Department.id.in_(payload.department_ids),Department.is_active.is_(True))).all() if payload.department_ids else []
    if len(depts)!=len(set(payload.department_ids)):raise HTTPException(status_code=422,detail="One or more departments are invalid or inactive.")
    user=User(email=email,password_hash=hash_password(payload.password),role=payload.role,is_active=True)
    db.add(user);db.flush()
    db.add_all([UserDepartment(user_id=user.id,department_id=d.id) for d in depts]);db.commit();db.refresh(user)
    return UserAdminResponse(id=user.id,email=user.email,role=user.role.value,is_active=user.is_active,department_ids=[d.id for d in depts])

@router.patch("/{user_id}",response_model=UserAdminResponse)
def update_user(user_id:UUID,payload:UserUpdate,admin:User=Depends(require_admin),db:Session=Depends(get_db)):
    user=db.get(User,user_id)
    if user is None:raise HTTPException(status_code=404,detail="User not found.")
    if user.id==admin.id and payload.is_active is False:raise HTTPException(status_code=409,detail="You cannot deactivate your own account.")
    if payload.role is not None:
        if user.role==Role.ADMIN and payload.role!=Role.ADMIN:
            count=db.scalar(select(func.count(User.id)).where(User.role==Role.ADMIN,User.is_active.is_(True))) or 0
            if count<=1:raise HTTPException(status_code=409,detail="Cannot demote last active administrator.")
        if user.id==admin.id and payload.role!=Role.ADMIN:raise HTTPException(status_code=409,detail="Cannot remove your own administrator role.")
        user.role=payload.role
    if payload.is_active is not None:
        if user.role==Role.ADMIN and not payload.is_active:
            count=db.scalar(select(func.count(User.id)).where(User.role==Role.ADMIN,User.is_active.is_(True))) or 0
            if count<=1:raise HTTPException(status_code=409,detail="Cannot deactivate last active administrator.")
        user.is_active=payload.is_active
    if payload.department_ids is not None:
        depts=db.scalars(select(Department).where(Department.id.in_(payload.department_ids),Department.is_active.is_(True))).all() if payload.department_ids else []
        if len(depts)!=len(set(payload.department_ids)):raise HTTPException(status_code=422,detail="One or more departments are invalid or inactive.")
        db.query(UserDepartment).filter(UserDepartment.user_id==user.id).delete(synchronize_session=False)
        db.add_all([UserDepartment(user_id=user.id,department_id=d.id) for d in depts])
    db.commit()
    ids=list(db.scalars(select(UserDepartment.department_id).where(UserDepartment.user_id==user.id)).all())
    return UserAdminResponse(id=user.id,email=user.email,role=user.role.value,is_active=user.is_active,department_ids=ids)
