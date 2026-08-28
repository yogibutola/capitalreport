import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from './auth';
import { ToastService } from '../shared/toast.service';
import { parseHttpError } from '../shared/http-error';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
    const authService = inject(AuthService);
    const router = inject(Router);
    const toast = inject(ToastService);
    const token = authService.getToken();

    const cloned = token
        ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
        : req;

    return next(cloned).pipe(
        catchError(err => {
            try {
                const parsed = parseHttpError(err);

                if (err.status === 401) {
                    // A 401 while already logged in means the session lapsed; on the
                    // login screen it just means bad credentials — let the form say so.
                    if (authService.isLoggedIn()) {
                        authService.logout();
                        toast.error('Your session has expired. Please sign in again.');
                        router.navigate(['/login']);
                    }
                } else if (parsed.kind === 'network' || parsed.kind === 'server') {
                    // System-wide failures: a global toast, per the error-handling spec.
                    toast.error(parsed.message);
                }
            } catch (sideEffectError) {
                console.error('Interceptor side-effect error:', sideEffectError);
            }

            return throwError(() => err);
        })
    );
};
