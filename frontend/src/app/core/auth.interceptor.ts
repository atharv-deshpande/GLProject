import { HttpInterceptorFn } from '@angular/common/http';
import { API_BASE_URL, AUTH_TOKEN_KEY } from './api-config';

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const token = typeof sessionStorage === 'undefined' ? null : sessionStorage.getItem(AUTH_TOKEN_KEY);
  if (!token || !request.url.startsWith(API_BASE_URL + '/')) return next(request);
  return next(request.clone({ setHeaders: { Authorization: `Bearer ${token}` } }));
};
