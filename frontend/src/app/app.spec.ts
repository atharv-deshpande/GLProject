import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { App } from './app';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [App], providers: [provideHttpClient()] }).compileComponents();
  });

  it('renders the secure sign-in screen when no session exists', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Sign in to EKIP');
    expect(compiled.querySelector('input[type="password"]')).toBeTruthy();
  });

  it('creates the workspace component', () => {
    const fixture = TestBed.createComponent(App);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('updates the selected workspace view', () => {
    const fixture = TestBed.createComponent(App);
    fixture.componentInstance.setView('knowledge');
    expect(fixture.componentInstance.activeView()).toBe('knowledge');
  });

  it('clears the session and returns to sign in on logout', () => {
    const fixture = TestBed.createComponent(App);
    fixture.componentInstance.logout();
    fixture.detectChanges();
    expect(fixture.componentInstance.isAuthenticated()).toBeFalse();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Sign in to EKIP');
  });
});
