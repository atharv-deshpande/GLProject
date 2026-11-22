import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'overview' },
  { path: 'overview', title: 'Overview · EKIP', loadComponent: () => import('./app').then((m) => m.App) },
  { path: '**', redirectTo: 'overview' },
];
