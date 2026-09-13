import { inject, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { Router, CanActivateFn } from '@angular/router';
import { AuthService } from './auth';

export const adminGuard: CanActivateFn = (route, state) => {
    const authService = inject(AuthService);
    const router = inject(Router);
    const platformId = inject(PLATFORM_ID);

    // The session lives in localStorage, which doesn't exist during SSR, so
    // there's no real auth state to check on the server. Let the server
    // render the requested URL; the client re-runs this guard on bootstrap
    // once AuthService has restored the real session.
    if (!isPlatformBrowser(platformId)) {
        return true;
    }

    if (authService.isAdmin()) {
        return true;
    }

    // Not an admin, redirect to admin login
    return router.createUrlTree(['/admin/login']);
};
