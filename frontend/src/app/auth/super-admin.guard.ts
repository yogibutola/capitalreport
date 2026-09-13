import { inject, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { Router, CanActivateFn } from '@angular/router';
import { AuthService } from './auth';

/**
 * Guards the hidden application-admin console. The route path itself is
 * unadvertised; this is the second line of defence (role check).
 */
export const superAdminGuard: CanActivateFn = () => {
    const authService = inject(AuthService);
    const router = inject(Router);
    const platformId = inject(PLATFORM_ID);

    // No localStorage during SSR, so there's no real session to check on the
    // server. Render the requested URL there; the client re-runs this guard
    // on bootstrap once AuthService has restored the real session.
    if (!isPlatformBrowser(platformId)) {
        return true;
    }

    if (authService.isSuperAdmin()) {
        return true;
    }

    return router.createUrlTree(['/x9k2-console/login']);
};
