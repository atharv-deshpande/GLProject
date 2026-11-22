import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, catchError, switchMap, tap, throwError } from 'rxjs';
import { API_BASE_URL, AUTH_TOKEN_KEY } from './api-config';

export interface UserProfile { id: string; email: string; role: 'ADMIN' | 'DEPARTMENT_MANAGER' | 'USER'; is_active: boolean; }
export interface DepartmentSummary { id: string; name: string; document_count: number; }
export interface DashboardSummary { total_documents: number; completed_documents: number; processing_documents: number; total_chunks: number; department_count: number; departments: DepartmentSummary[]; }
export interface LibraryDocument { id: string; name: string; file_type: string; department_id: string; department_name: string; status: string; created_at: string; }
export interface LibraryResponse { items: LibraryDocument[]; total: number; }
export interface SearchHit { chunk_id: string; document_id: string; document_name: string; department_id: string; page_number: number | null; section_title: string | null; content: string; score: number; }
export interface SearchResponse { query: string; results: SearchHit[]; total: number; }
export interface Citation { source_id: string; document_id: string; document_name: string; page_number: number | null; section_title: string | null; chunk_id: string; }
export interface ChatResponse { query: string; answer: string; citations: Citation[]; insufficient_evidence: boolean; }
export interface UploadResponse { document_id: string; document_name: string; file_type: string; status: string; file_size: number; total_chunks: number; total_tokens: number; department_id: string; version_number: number; checksum: string; metadata: Record<string, unknown>; }
interface TokenResponse { access_token: string; token_type: string; }

@Injectable({ providedIn: 'root' })
export class EkipApiService {
  private readonly http = inject(HttpClient);
  private readonly base = API_BASE_URL;

  get token(): string | null {
    return typeof sessionStorage === 'undefined' ? null : sessionStorage.getItem(AUTH_TOKEN_KEY);
  }
  get isAuthenticated(): boolean { return !!this.token; }

  authenticate(email: string, password: string): Observable<UserProfile> {
    return this.http.post<TokenResponse>(`${this.base}/auth/login`, { email, password }).pipe(
      tap((result) => sessionStorage.setItem(AUTH_TOKEN_KEY, result.access_token)),
      switchMap(() => this.me()),
      catchError((error) => { this.logout(); return throwError(() => error); }),
    );
  }
  me(): Observable<UserProfile> { return this.http.get<UserProfile>(`${this.base}/users/me`); }
  dashboard(): Observable<DashboardSummary> { return this.http.get<DashboardSummary>(`${this.base}/dashboard/summary`); }
  documents(departmentId: string | null, search: string): Observable<LibraryResponse> {
    let params = new HttpParams().set('limit', '100');
    if (departmentId) params = params.set('department_id', departmentId);
    if (search.trim()) params = params.set('search', search.trim());
    return this.http.get<LibraryResponse>(`${this.base}/library/documents`, { params });
  }
  upload(file: File, departmentId: string): Observable<UploadResponse> {
    const form = new FormData();
    form.append('file', file, file.name);
    form.append('department_id', departmentId);
    return this.http.post<UploadResponse>(`${this.base}/documents/upload`, form);
  }
  indexDocument(documentId: string): Observable<{ document_id: string; indexed_chunks: number; status: string }> {
    return this.http.post<{ document_id: string; indexed_chunks: number; status: string }>(`${this.base}/documents/${documentId}/index`, {});
  }
  search(query: string, departmentId: string | null): Observable<SearchResponse> {
    return this.http.post<SearchResponse>(`${this.base}/search`, { query, department_id: departmentId, top_k: 5 });
  }
  chat(query: string, departmentId: string | null): Observable<ChatResponse> {
    return this.http.post<ChatResponse>(`${this.base}/chat`, { query, department_id: departmentId, top_k: 5 });
  }
  logout(): void { if (typeof sessionStorage !== 'undefined') sessionStorage.removeItem(AUTH_TOKEN_KEY); }
}
