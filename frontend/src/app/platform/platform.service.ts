import { Injectable, signal, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, catchError, throwError, tap } from 'rxjs';
import { ToastService } from '../shared/toast.service';
import { ConfirmService } from '../shared/confirm.service';
import { parseHttpError } from '../shared/http-error';

const BASE = '/api/v1/platform-console';

export interface PlatformClub {
  id: string;
  email: string;
  clubName: string | null;
  address: string | null;
  phone: string | null;
  league_count: number;
  tournament_count: number;
}

export interface PlatformPlayer {
  id: string;
  email: string;
  firstName: string | null;
  lastName: string | null;
  dupr_rating: number | null;
  state: string | null;
  city: string | null;
  zip_code: string | null;
  league_count: number;
}

export interface ActivityEntry {
  id: string;
  ts: string;
  actor: string;
  actor_role: string | null;
  method: string;
  path: string;
  action: string;
  status_code: number;
  duration_ms: number;
}

export interface PlatformMetrics {
  total_clubs: number;
  total_players: number;
  total_leagues: number;
  total_tournaments: number;
  actions_24h: number;
  active_actors_24h: number;
  signins_7d: number;
  errors_24h: number;
}

export interface NewClub {
  clubName: string;
  email: string;
  password: string;
  address?: string;
  phone?: string;
}

export interface NewPlayer {
  firstName: string;
  lastName: string;
  email: string;
  password: string;
  dupr_rating: number;
}

@Injectable({ providedIn: 'root' })
export class PlatformService {
  private http = inject(HttpClient);
  private toast = inject(ToastService);
  private confirm = inject(ConfirmService);

  clubs = signal<PlatformClub[]>([]);
  players = signal<PlatformPlayer[]>([]);
  activity = signal<ActivityEntry[]>([]);
  metrics = signal<PlatformMetrics | null>(null);
  loading = signal(false);

  refreshAll() {
    this.fetchClubs();
    this.fetchPlayers();
    this.fetchMetrics();
    this.fetchActivity();
  }

  fetchClubs() {
    this.http.get<PlatformClub[]>(`${BASE}/clubs`).subscribe({
      next: (data) => this.clubs.set(data),
      error: (err) => this.toast.error(parseHttpError(err).message),
    });
  }

  fetchPlayers() {
    this.http.get<PlatformPlayer[]>(`${BASE}/players`).subscribe({
      next: (data) => this.players.set(data),
      error: (err) => this.toast.error(parseHttpError(err).message),
    });
  }

  fetchMetrics() {
    this.http.get<PlatformMetrics>(`${BASE}/metrics`).subscribe({
      next: (data) => this.metrics.set(data),
      error: (err) => this.toast.error(parseHttpError(err).message),
    });
  }

  fetchActivity(filters: { actor?: string; action?: string; since?: string } = {}) {
    let params = new HttpParams();
    if (filters.actor) params = params.set('actor', filters.actor);
    if (filters.action) params = params.set('action', filters.action);
    if (filters.since) params = params.set('since', filters.since);
    this.loading.set(true);
    this.http.get<ActivityEntry[]>(`${BASE}/activity`, { params }).subscribe({
      next: (data) => {
        this.activity.set(data);
        this.loading.set(false);
      },
      error: (err) => {
        this.loading.set(false);
        this.toast.error(parseHttpError(err).message);
      },
    });
  }

  addClub(club: NewClub): Observable<unknown> {
    return this.http.post(`${BASE}/clubs`, club).pipe(
      tap(() => {
        this.toast.success(`Club "${club.clubName}" created.`);
        this.fetchClubs();
        this.fetchMetrics();
      }),
      catchError((err) => throwError(() => parseHttpError(err))),
    );
  }

  addPlayer(player: NewPlayer): Observable<unknown> {
    return this.http.post(`${BASE}/players`, player).pipe(
      tap(() => {
        this.toast.success(`Player "${player.firstName} ${player.lastName}" created.`);
        this.fetchPlayers();
        this.fetchMetrics();
      }),
      catchError((err) => throwError(() => parseHttpError(err))),
    );
  }

  async removeClub(club: PlatformClub) {
    const confirmed = await this.confirm.ask({
      title: `Remove ${club.clubName || club.email}?`,
      message:
        'The club account is deleted. Its existing leagues and tournaments are left in place but will no longer have an owner. This cannot be undone.',
      confirmLabel: 'Remove Club',
      cancelLabel: 'Keep Club',
      tone: 'danger',
    });
    if (!confirmed) return;

    const snapshot = this.clubs();
    this.clubs.update((c) => c.filter((x) => x.email !== club.email));
    this.http.delete(`${BASE}/clubs/${encodeURIComponent(club.email)}`).subscribe({
      next: () => {
        this.toast.success('Club removed.');
        this.fetchMetrics();
      },
      error: (err) => {
        this.clubs.set(snapshot);
        this.toast.error(parseHttpError(err).message);
      },
    });
  }

  async removePlayer(player: PlatformPlayer) {
    const name = `${player.firstName ?? ''} ${player.lastName ?? ''}`.trim() || player.email;
    const confirmed = await this.confirm.ask({
      title: `Remove ${name}?`,
      message:
        'The player account is deleted and the player is removed from every league and tournament roster. Recorded match results are kept. This cannot be undone.',
      confirmLabel: 'Remove Player',
      cancelLabel: 'Keep Player',
      tone: 'danger',
    });
    if (!confirmed) return;

    const snapshot = this.players();
    this.players.update((p) => p.filter((x) => x.email !== player.email));
    this.http.delete(`${BASE}/players/${encodeURIComponent(player.email)}`).subscribe({
      next: () => {
        this.toast.success('Player removed.');
        this.fetchMetrics();
      },
      error: (err) => {
        this.players.set(snapshot);
        this.toast.error(parseHttpError(err).message);
      },
    });
  }
}
