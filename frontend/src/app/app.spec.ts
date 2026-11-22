import { TestBed } from '@angular/core/testing';
import { App } from './app';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [App] }).compileComponents();
  });

  it('creates the workspace shell', () => {
    const fixture = TestBed.createComponent(App);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('renders the EKIP overview by default', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h1')?.textContent).toContain('Good morning');
    expect(compiled.textContent).toContain('Knowledge activity');
    expect(compiled.textContent).toContain('Department coverage');
  });

  it('switches to the knowledge assistant view', () => {
    const fixture = TestBed.createComponent(App);
    fixture.componentInstance.setView('knowledge');
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h1')?.textContent).toContain('Ask EKIP');
    expect(compiled.textContent).toContain('Search scope');
  });

  it('filters document list by selected department', () => {
    const fixture = TestBed.createComponent(App);
    fixture.componentInstance.setDepartment('Payments');
    expect(fixture.componentInstance.filteredDocuments().length).toBe(1);
    expect(fixture.componentInstance.filteredDocuments()[0].department).toBe('Payments');
  });
});
