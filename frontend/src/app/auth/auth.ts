import { Injectable, signal, PLATFORM_ID, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { isPlatformBrowser } from '@angular/common';
import { Observable, throwError } from 'rxjs';
import { tap, catchError, map } from 'rxjs/operators';
import { parseHttpError } from '../shared/http-error';

export interface User {
  id: string;
  firstName: string;
  lastName: string;
  userName: string;
  email: string;
  dupr_rating: number;
  role?: 'player' | 'admin';
  token?: string;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private platformId = inject(PLATFORM_ID);
  private http = inject(HttpClient);

  // Signal to hold current user
  currentUser = signal<User | null>(null);

  constructor() {
    // Check local storage for persisted user (only in browser)
    if (isPlatformBrowser(this.platformId)) {
      const stored = localStorage.getItem('pickleball_user');
      if (stored) {
        try {
          const user = JSON.parse(stored);
          // Validate token existence. If missing (stale session), clear it.
          if (user && user.token) {
            this.currentUser.set(user);
          } else {
            console.warn('Found stale user session without token. Clearing session.');
            localStorage.removeItem('pickleball_user');
            this.currentUser.set(null);
          }
        } catch (e) {
          console.error('Error parsing stored user:', e);
          localStorage.removeItem('pickleball_user');
        }
      }
    }
  }

  signinObservable(email: string, password: string): Observable<boolean> {
    const payload = { email, password };

    return this.http.post<any>('api/v1/signin', payload).pipe(
      tap((response) => {
        const user: User = {
          id: response.id || crypto.randomUUID(),
          firstName: response.firstName || '',
          lastName: response.lastName || '',
          userName: response.userName || '',
          email: response.email || email,
          dupr_rating: response.dupr_rating || 0,
          role: response.role || 'player',
          token: response.token
        };

        this.currentUser.set(user);

        if (isPlatformBrowser(this.platformId)) {
          localStorage.setItem('pickleball_user', JSON.stringify(user));
        }
      }),
      map(() => true),
      catchError((err) => {
        const parsed = parseHttpError(err);
        // 401 here = bad credentials, not an expired session. Give the form
        // something actionable rather than the raw "Unauthorized".
        if (parsed.kind === 'auth' && !Object.keys(parsed.fieldErrors).length) {
          parsed.message = 'Email or password is incorrect. Please try again.';
        }
        return throwError(() => parsed);
      })
    );
  }

  getToken(): string | undefined {
    return this.currentUser()?.token;
  }

  isAdmin(): boolean {
    return this.currentUser()?.role === 'admin';
  }

  // Observable-based signup that returns result for proper async handling
  signupObservable(firstName: string, lastName: string, email: string, password: string, duprRating: number): Observable<boolean> {
    const username = `${firstName.toLowerCase()}.${lastName.toLowerCase()}`;

    const signupPayload = {
      firstName: firstName,
      lastName: lastName,
      userName: username,
      email: email,
      password: password,
      dupr_rating: duprRating
    };

    return this.http.post<any>('api/v1/signup', signupPayload).pipe(
      tap((response) => {
        const user: User = {
          id: response.id || crypto.randomUUID(),
          firstName: firstName,
          lastName: lastName,
          userName: username,
          email,
          dupr_rating: duprRating,
          role: response.role || 'player',
          token: response.token
        };

        this.currentUser.set(user);

        if (isPlatformBrowser(this.platformId)) {
          localStorage.setItem('pickleball_user', JSON.stringify(user));
        }
      }),
      map(() => true),
      catchError((err) => throwError(() => parseHttpError(err)))
    );
  }

  // Club Signup
  signupClubObservable(clubName: string, email: string, password: string, address: string, phone: string): Observable<boolean> {
    const payload = {
      clubName,
      email,
      password,
      address,
      phone
    };

    return this.http.post<any>('api/v1/signup/club', payload).pipe(
      tap((response) => {
        const user: User = {
          id: response.id || crypto.randomUUID(),
          firstName: clubName, // Map clubName to firstName as per requirement
          lastName: '',
          userName: `admin.${clubName.toLowerCase().replace(/\s+/g, '')}`,
          email,
          dupr_rating: 0,
          role: 'admin', // Club signup always results in admin role
          token: response.token
        };

        this.currentUser.set(user);

        if (isPlatformBrowser(this.platformId)) {
          localStorage.setItem('pickleball_user', JSON.stringify(user));
        }
      }),
      map(() => true),
      catchError((err) => throwError(() => parseHttpError(err)))
    );
  }

  logout() {
    this.currentUser.set(null);
    if (isPlatformBrowser(this.platformId)) {
      localStorage.removeItem('pickleball_user');
    }
  }

  isLoggedIn() {
    return this.currentUser() !== null;
  }
}
