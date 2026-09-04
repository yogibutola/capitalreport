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
  age?: number | null;
  state?: string | null;
  city?: string | null;
  clubName?: string | null;
  address?: string | null;
  phone?: string | null;
  role?: 'player' | 'admin';
  token?: string;
}

export interface Profile {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  age: number | null;
  dupr_rating: number | null;
  state: string | null;
  city: string | null;
  clubName: string | null;
  address: string | null;
  phone: string | null;
  role: 'player' | 'admin';
  token?: string | null;
}

/** Fields a player may edit. */
export interface PlayerProfileUpdate {
  firstName: string;
  lastName: string;
  email: string;
  age: number | null;
  dupr_rating: number | null;
  state: string | null;
  city: string | null;
}

/** Fields a club (admin) may edit. */
export interface ClubProfileUpdate {
  clubName: string;
  email: string;
  address: string | null;
  phone: string | null;
}

export type ProfileUpdate = PlayerProfileUpdate | ClubProfileUpdate;

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

  /** Load the authenticated user's full profile from the backend. */
  getProfile(): Observable<Profile> {
    return this.http.get<Profile>('api/v1/profile').pipe(
      catchError((err) => throwError(() => parseHttpError(err)))
    );
  }

  /** Persist profile edits, then sync the cached session with the result. */
  updateProfile(data: ProfileUpdate): Observable<Profile> {
    return this.http.put<Profile>('api/v1/profile', data).pipe(
      tap((profile) => this.applyProfile(profile)),
      catchError((err) => throwError(() => parseHttpError(err)))
    );
  }

  /** Change the signed-in user's password. */
  changePassword(currentPassword: string, newPassword: string): Observable<void> {
    return this.http
      .post<unknown>('api/v1/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      })
      .pipe(
        map(() => undefined),
        catchError((err) => throwError(() => parseHttpError(err)))
      );
  }

  /** Request a password-reset link for the given email. */
  forgotPassword(email: string): Observable<void> {
    return this.http.post<unknown>('api/v1/forgot-password', { email }).pipe(
      map(() => undefined),
      catchError((err) => throwError(() => parseHttpError(err)))
    );
  }

  /** Set a new password using a token from a reset-password email link. */
  resetPassword(token: string, newPassword: string): Observable<void> {
    return this.http
      .post<unknown>('api/v1/reset-password', { token, new_password: newPassword })
      .pipe(
        map(() => undefined),
        catchError((err) => throwError(() => parseHttpError(err)))
      );
  }

  /** Merge a fresh profile into the current session + localStorage. */
  private applyProfile(profile: Profile): void {
    const current = this.currentUser();
    if (!current) return;

    const updated: User = {
      ...current,
      firstName: profile.firstName ?? current.firstName,
      lastName: profile.lastName ?? current.lastName,
      email: profile.email ?? current.email,
      dupr_rating: profile.dupr_rating ?? current.dupr_rating,
      age: profile.age ?? null,
      state: profile.state ?? null,
      city: profile.city ?? null,
      clubName: profile.clubName ?? null,
      address: profile.address ?? null,
      phone: profile.phone ?? null,
      role: profile.role ?? current.role,
      // Backend only returns a token when the email changed and the old one is stale.
      token: profile.token || current.token,
    };

    this.currentUser.set(updated);
    if (isPlatformBrowser(this.platformId)) {
      localStorage.setItem('pickleball_user', JSON.stringify(updated));
    }
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
