import { Component, computed, signal } from '@angular/core';

type ViewKey = 'overview' | 'knowledge' | 'documents' | 'departments' | 'activity';

@Component({
  selector: 'app-root',
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  readonly activeView = signal<ViewKey>('overview');
  readonly mobileNavOpen = signal(false);
  readonly searchText = signal('');
  readonly question = signal('');
  readonly answerVisible = signal(false);
  readonly selectedDepartment = signal('All departments');
  readonly selectedPeriod = signal('Last 30 days');
  readonly uploadFileName = signal('');
  readonly notice = signal('');
  readonly navItems: { key: ViewKey; label: string; icon: string; section: string }[] = [
    { key: 'overview', label: 'Overview', icon: '◫', section: 'WORKSPACE' },
    { key: 'knowledge', label: 'Ask knowledge', icon: '✳', section: 'WORKSPACE' },
    { key: 'documents', label: 'Documents', icon: '▤', section: 'WORKSPACE' },
    { key: 'departments', label: 'Departments', icon: '▦', section: 'MANAGE' },
    { key: 'activity', label: 'Activity log', icon: '◷', section: 'MANAGE' },
  ];
  readonly currentTitle = computed(() => ({
    overview: 'Overview',
    knowledge: 'Knowledge assistant',
    documents: 'Document library',
    departments: 'Departments',
    activity: 'Activity log',
  })[this.activeView()]);
  readonly documents = [
    { name: 'Retail Lending — Credit Policy v4.2', type: 'PDF', department: 'Retail Banking', date: 'Today, 10:42 AM', status: 'Indexed', pages: '42 pages', initials: 'RL', tone: 'blue' },
    { name: 'UPI Dispute Resolution Playbook', type: 'DOCX', department: 'Payments', date: 'Yesterday, 4:18 PM', status: 'Indexed', pages: '18 pages', initials: 'UP', tone: 'mint' },
    { name: 'Card Operations — Chargeback SOP', type: 'PDF', department: 'Cards', date: 'Nov 18, 2026', status: 'Processing', pages: '26 pages', initials: 'CO', tone: 'violet' },
    { name: 'KYC & Customer Due Diligence', type: 'PDF', department: 'Risk & Compliance', date: 'Nov 17, 2026', status: 'Indexed', pages: '64 pages', initials: 'KY', tone: 'amber' },
  ];
  readonly filteredDocuments = computed(() => {
    const q = this.searchText().toLowerCase().trim();
    const department = this.selectedDepartment();
    return this.documents.filter((doc) =>
      (!q || (doc.name + ' ' + doc.department + ' ' + doc.type).toLowerCase().includes(q)) &&
      (department === 'All departments' || doc.department === department)
    );
  });
  readonly departments = [
    { name: 'Retail Banking', description: 'Loans, deposits & branch operations', count: 128, people: 24, color: 'blue', initials: 'RB' },
    { name: 'Payments', description: 'UPI, NEFT, RTGS & payment rails', count: 96, people: 18, color: 'mint', initials: 'PY' },
    { name: 'Cards', description: 'Credit, debit & card operations', count: 84, people: 16, color: 'violet', initials: 'CD' },
    { name: 'Risk & Compliance', description: 'KYC, AML, audit & regulatory', count: 72, people: 12, color: 'amber', initials: 'RC' },
    { name: 'Technology', description: 'Platforms, infrastructure & security', count: 54, people: 21, color: 'slate', initials: 'TE' },
  ];

  setView(view: ViewKey): void {
    this.activeView.set(view);
    this.mobileNavOpen.set(false);
    this.notice.set('');
  }

  askQuestion(): void {
    const q = this.question().trim();
    if (!q) {
      this.notice.set('Enter a question to search your knowledge base.');
      return;
    }
    this.notice.set('Connect the assistant to POST /api/v1/chat to retrieve live answers.');
    this.answerVisible.set(true);
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    const allowed = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/html'];
    if (!allowed.includes(file.type) && !/\.(pdf|docx|html?)$/i.test(file.name)) {
      this.notice.set('Choose a PDF, DOCX or HTML document.');
      input.value = '';
      return;
    }
    this.uploadFileName.set(file.name);
    this.notice.set('File selected. Connect this upload panel to POST /api/v1/documents/upload with a department ID and Bearer token.');
  }

  clearNotice(): void { this.notice.set(''); }
  setDepartment(value: string): void { this.selectedDepartment.set(value); }
}
