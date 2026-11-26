import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { EkipApiService, UserProfile, DashboardSummary, LibraryDocument, ChatResponse, SearchHit, AdminUser } from './core/ekip-api.service';

type ViewKey = 'overview' | 'knowledge' | 'documents' | 'departments' | 'activity';

@Component({
  selector: 'app-root',
  imports: [FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
interface ChatHistoryItem { id: string; user_id: string; email: string; prompt: string; answer: string; input_tokens: number; output_tokens: number; duration_ms: number; created_at: string; }
interface ChatUsage { input_tokens?: number; output_tokens?: number; chat_sessions?: number; usage_time_ms?: number; total_input_tokens?: number; total_output_tokens?: number; users?: Array<{email:string;input_tokens:number;output_tokens:number}>; }

export class App {
  readonly api = inject(EkipApiService);
  readonly activeView = signal<ViewKey>('overview');
  readonly mobileNavOpen = signal(false);
  readonly searchText = signal('');
  readonly question = signal('');
  readonly selectedDepartmentId = signal('');
  readonly selectedDepartmentName = signal('All departments');
  readonly notice = signal('');
  readonly error = signal('');
  readonly loading = signal(false);
  readonly loginEmail = signal('');
  readonly loginPassword = signal('');
  readonly user = signal<UserProfile | null>(null);
  readonly dashboard = signal<DashboardSummary | null>(null);
  readonly documents = signal<LibraryDocument[]>([]);
  readonly documentTotal = signal(0);
  readonly answer = signal<ChatResponse | null>(null);
  readonly searchResults = signal<SearchHit[]>([]);
  readonly uploadFile = signal<File | null>(null);
  readonly uploadBusy = signal(false);
  readonly chatBusy = signal(false);
  readonly loginBusy = signal(false);
  readonly adminUsers = signal<AdminUser[]>([]);
  readonly adminEmail = signal('');
  readonly adminPassword = signal('');
  readonly adminRole = signal<AdminUser['role']>('USER');
  readonly adminDepartmentIds = signal<string[]>([]);
  readonly selectedAdminUserId = signal('');
  readonly selectedUserDepartmentIds = signal<string[]>([]);
  readonly chatHistory = signal<ChatHistoryItem[]>([]);
  readonly usage = signal<ChatUsage | null>(null);
  readonly adminBusy = signal(false);
  readonly currentTitle = computed(() => ({
    overview: 'Overview', knowledge: 'Knowledge assistant', documents: 'Document library',
    departments: 'Departments', activity: 'Activity log',
  })[this.activeView()]);
  readonly isAuthenticated = computed(() => !!this.user());
  readonly departments = computed(() => this.dashboard()?.departments ?? []);
  readonly filteredDocuments = computed(() => {
    const q = this.searchText().toLowerCase().trim();
    return this.documents().filter((doc) =>
      !q || (doc.name + ' ' + doc.department_name + ' ' + doc.file_type).toLowerCase().includes(q)
    );
  });

  constructor() {
    if (this.api.isAuthenticated) {
      this.loading.set(true);
      this.api.me().subscribe({
        next: (profile) => { this.user.set(profile); this.loadWorkspace(); },
        error: () => { this.api.logout(); this.loading.set(false); },
      });
    }
  }

  login(): void {
    this.error.set('');
    if (!this.loginEmail().trim() || !this.loginPassword()) {
      this.error.set('Enter your work email and password.');
      return;
    }
    this.loginBusy.set(true);
    this.api.authenticate(this.loginEmail().trim(), this.loginPassword()).subscribe({
      next: (profile) => {
        this.user.set(profile);
        this.loginPassword.set('');
        this.loginBusy.set(false);
        this.loadWorkspace();
      },
      error: (err: HttpErrorResponse) => {
        this.loginBusy.set(false);
        this.error.set(this.errorMessage(err, 'Unable to sign in. Check your credentials and API connection.'));
      },
    });
  }

  logout(): void {
    this.api.logout();
    this.user.set(null);
    this.dashboard.set(null);
    this.documents.set([]);
    this.answer.set(null);
    this.activeView.set('overview');
    this.notice.set('You have been signed out.');
  }

  loadWorkspace(): void {
    this.loading.set(true);
    this.error.set('');
    this.api.dashboard().subscribe({
      next: (summary) => {
        this.dashboard.set(summary);
        this.loading.set(false);
        this.loadDocuments();
      },
      error: (err: HttpErrorResponse) => {
        this.loading.set(false);
        this.error.set(this.errorMessage(err, 'Unable to load dashboard metrics.'));
      },
    });
  }

  loadDocuments(): void {
    const departmentId = this.selectedDepartmentId() || null;
    this.api.documents(departmentId, this.searchText()).subscribe({
      next: (result) => { this.documents.set(result.items); this.documentTotal.set(result.total); },
      error: (err: HttpErrorResponse) => this.error.set(this.errorMessage(err, 'Unable to load documents.')),
    });
  }

  setView(view: ViewKey): void {
    this.activeView.set(view);
    this.mobileNavOpen.set(false);
    this.notice.set('');
    this.error.set('');
    if (view === 'documents') this.loadDocuments();
    if (view === 'departments' && this.user()?.role === 'ADMIN') this.loadAdminUsers();
  }

  setDepartment(id: string): void {
    this.selectedDepartmentId.set(id);
    const selected = this.departments().find((d) => d.id === id);
    this.selectedDepartmentName.set(selected?.name ?? 'All departments');
    this.loadDocuments();
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    if (!file) return;
    if (!/\.(pdf|docx|html?)$/i.test(file.name)) {
      this.error.set('Choose a PDF, DOCX or HTML document.');
      input.value = '';
      return;
    }
    this.uploadFile.set(file);
    this.notice.set(`Selected ${file.name}. Choose a department and upload when ready.`);
  }

  uploadSelected(): void {
    const file = this.uploadFile();
    const departmentId = this.selectedDepartmentId();
    if (!file) { this.error.set('Choose a document first.'); return; }
    if (!departmentId) { this.error.set('Select a department before uploading.'); return; }
    this.uploadBusy.set(true);
    this.error.set('');
    this.api.upload(file, departmentId).subscribe({
      next: (result) => {
        this.notice.set(`Uploaded ${result.document_name}. ${result.total_chunks} chunks were created. Starting vector indexing…`);
        this.uploadBusy.set(false);
        this.uploadFile.set(null);
        this.loadDocuments();
        this.loadWorkspace();
        this.api.indexDocument(result.document_id).subscribe({
          next: (indexed) => { this.notice.set(`Document indexed successfully: ${indexed.indexed_chunks} chunks.`); this.loadWorkspace(); },
          error: (err: HttpErrorResponse) => this.error.set(this.errorMessage(err, 'Document was saved, but vector indexing failed. Retry indexing after checking Ollama and Qdrant.')),
        });
      },
      error: (err: HttpErrorResponse) => {
        this.uploadBusy.set(false);
        this.error.set(this.errorMessage(err, 'Document upload failed.'));
      },
    });
  }

  askQuestion(): void {
    const q = this.question().trim();
    if (q.length < 2) { this.error.set('Enter a question with at least 2 characters.'); return; }
    this.chatBusy.set(true);
    this.error.set('');
    this.answer.set(null);
    this.api.chat(q, this.selectedDepartmentId() || null).subscribe({
      next: (result) => { this.answer.set(result); this.chatBusy.set(false); },
      error: (err: HttpErrorResponse) => { this.chatBusy.set(false); this.error.set(this.errorMessage(err, 'The knowledge assistant could not complete this request.')); },
    });
  }

  runSearch(): void {
    const q = this.question().trim();
    if (q.length < 2) { this.error.set('Enter a search phrase with at least 2 characters.'); return; }
    this.chatBusy.set(true);
    this.api.search(q, this.selectedDepartmentId() || null).subscribe({
      next: (result) => { this.searchResults.set(result.results); this.chatBusy.set(false); },
      error: (err: HttpErrorResponse) => { this.chatBusy.set(false); this.error.set(this.errorMessage(err, 'Knowledge search failed.')); },
    });
  }


  loadAdminUsers(): void {
    if (this.user()?.role !== 'ADMIN') return;
    this.api.users().subscribe({
      next: (users) => {
        this.adminUsers.set(users);
        if (!this.selectedAdminUserId() && users.length) this.selectAdminUser(users[0].id);
      },
      error: (err: HttpErrorResponse) => this.error.set(this.errorMessage(err, 'Unable to load users.')),
    });
  }

  onNewUserDepartmentsChanged(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.adminDepartmentIds.set(Array.from(select.selectedOptions, option => option.value));
  }

  onExistingUserDepartmentsChanged(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.selectedUserDepartmentIds.set(Array.from(select.selectedOptions, option => option.value));
  }

  selectAdminUser(userId: string): void {
    this.selectedAdminUserId.set(userId);
    const selected = this.adminUsers().find(user => user.id === userId);
    this.selectedUserDepartmentIds.set(selected?.department_ids ?? []);
  }

  createAdminUser(): void {
    if (this.user()?.role !== 'ADMIN') return;
    const email = this.adminEmail().trim().toLowerCase();
    const password = this.adminPassword();
    if (!email || password.length < 8) {
      this.error.set('Enter an email and a password of at least 12 characters.');
      return;
    }
    this.adminBusy.set(true);
    this.api.createUser({
      email,
      password,
      role: this.adminRole(),
      department_ids: this.adminDepartmentIds(),
    }).subscribe({
      next: (created) => {
        this.adminBusy.set(false);
        this.adminPassword.set('');
        this.adminEmail.set('');
        this.adminDepartmentIds.set([]);
        this.notice.set(`Created ${created.email} with ${created.department_ids.length} department assignment(s).`);
        this.loadAdminUsers();
      },
      error: (err: HttpErrorResponse) => {
        this.adminBusy.set(false);
        this.error.set(this.errorMessage(err, 'Unable to create user.'));
      },
    });
  }

  saveUserDepartments(): void {
    if (this.user()?.role !== 'ADMIN' || !this.selectedAdminUserId()) return;
    this.adminBusy.set(true);
    this.api.updateUser(this.selectedAdminUserId(), {
      department_ids: this.selectedUserDepartmentIds(),
    }).subscribe({
      next: (updated) => {
        this.adminBusy.set(false);
        this.notice.set(`Updated department access for ${updated.email}.`);
        this.loadAdminUsers();
      },
      error: (err: HttpErrorResponse) => {
        this.adminBusy.set(false);
        this.error.set(this.errorMessage(err, 'Unable to update department access.'));
      },
    });
  }

  loadChatData(): void {\n    this.api.chatHistory().subscribe({next: rows => this.chatHistory.set(rows), error: () => this.chatHistory.set([])});\n    this.api.chatUsage().subscribe({next: usage => this.usage.set(usage), error: () => this.usage.set(null)});\n  }\n\n  formatUsageTime(ms: number): string {\n    const seconds = Math.floor(ms / 1000);\n    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;\n  }\n\n  formatDate(value: string): string {
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value));
  }
  errorMessage(err: HttpErrorResponse, fallback: string): string {
    if (err.status === 0) return 'Cannot reach the EKIP API. Check that FastAPI is running at http://localhost:8000.';
    if (err.status === 401) { this.logout(); return 'Your session expired. Please sign in again.'; }
    if (err.status === 403) return err.error?.detail ?? 'You do not have permission for this department or action.';
    return err.error?.detail ?? fallback;
  }
  clearMessages(): void { this.notice.set(''); this.error.set(''); }
}
