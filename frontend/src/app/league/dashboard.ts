import { Component, computed, effect, inject, PLATFORM_ID, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe, CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient, HttpParams } from '@angular/common/http';
import { AuthService } from '../auth/auth';
import { PlayerService } from '../player/player';
import { FormsModule } from '@angular/forms';
import { GroupsService, GroupEvent } from '../groups/groups.service';
import { MatchService } from '../matches/match';
import { PaddleChipsComponent } from '../shared/paddle-chips';
import { Paddle } from '../shared/paddle';

interface UpcomingGroupEvent {
    groupId: string;
    groupName: string;
    event: GroupEvent;
}

interface PlayerResult {
    id: string;
    firstName: string;
    lastName: string;
    email: string;
    dupr_rating: number | null;
    role: string;
    city?: string | null;
    state?: string | null;
    paddles?: Paddle[];
    /** Miles from the search origin; null unless a radius was applied. */
    distance_miles?: number | null;
}

interface PlayerSearchResponse {
    results: PlayerResult[];
    count: number;
    origin_zip: string | null;
    radius_miles: number | null;
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterLink, CommonModule, FormsModule, PaddleChipsComponent],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css'
})
export class DashboardComponent {
  private authService = inject(AuthService);
  private router = inject(Router);
  private platformId = inject(PLATFORM_ID);
  private http = inject(HttpClient);
  private groupsService = inject(GroupsService);
  private matchService = inject(MatchService);
  protected playerService = inject(PlayerService);

  currentUser = this.authService.currentUser;
  leagues = this.playerService.getLeagues;
  upcomingMatches = this.playerService.getUpcomingMatches;
  availableLeagues = this.playerService.getAvailableLeagues;

  // Premium banking visual states
  welcomeTimestamp = '';

  // Player search. Filtering happens server-side, so there is deliberately no
  // client-side roster cache - it would silently ignore these filters.
  searchFirstName = '';
  searchLastName = '';
  searchDuprMin: number | null = null;
  searchDuprMax: number | null = null;
  searchRadiusMiles: number | null = null;
  /** A signal, not a plain field: it's written from async callbacks, and the app is
   *  zoneless, so a plain field wouldn't repaint the input. */
  searchZip = signal('');
  searchResults = signal<PlayerResult[]>([]);
  isSearching = signal(false);
  searchError = signal<string | null>(null);
  /** Set when the failure was about the origin ZIP, so it renders by that field. */
  zipError = signal<string | null>(null);
  hasSearched = signal(false);
  /** The radius the current results were actually filtered by. */
  appliedRadius = signal<number | null>(null);
  /** Prefill runs once per component, not once per effect pass. */
  private zipLookedUp = false;

  /** Both bounds are optional, but an inverted range is never valid. */
  get duprRangeInvalid(): boolean {
    return this.searchDuprMin != null && this.searchDuprMax != null
      && this.searchDuprMax < this.searchDuprMin;
  }

  get nextMatch() {
    const matches = this.upcomingMatches();
    if (!matches.length) return null;
    return [...matches].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())[0];
  }

  get latestAvailableLeague() {
    return this.availableLeagues()[0] ?? null;
  }

  // Last 5 completed games (across all leagues/tournaments) as W/L, oldest → most recent
  get lastFiveResults(): ('W' | 'L')[] {
    const email = this.currentUser()?.email?.toLowerCase();
    if (!email) return [];

    const isMe = (p: any) => (p?.email || '').toLowerCase() === email;

    return this.matchService.getMatches()()
      .filter(m => {
        const t1 = m.team_one, t2 = m.team_two;
        if (!t1 || !t2) return false;
        const statusLower = String(m.match_status || '').toLowerCase();
        const isCompleted = statusLower === 'completed' || Number(t1.score || 0) > 0 || Number(t2.score || 0) > 0;
        if (!isCompleted) return false;
        return [t1.player_one, t1.player_two, t2.player_one, t2.player_two].some(isMe);
      })
      .sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime())
      .slice(0, 5)
      .reverse()
      .map(m => {
        const t1 = m.team_one, t2 = m.team_two;
        const isTeam1 = [t1.player_one, t1.player_two].some(isMe);
        const s1 = Number(t1.score || 0), s2 = Number(t2.score || 0);
        const won = isTeam1 ? s1 > s2 : s2 > s1;
        return won ? 'W' : 'L';
      });
  }

  get lastFiveRecord(): string {
    const results = this.lastFiveResults;
    const wins = results.filter(r => r === 'W').length;
    return `${wins}W - ${results.length - wins}L`;
  }

  formatLeagueDates(start: Date, end: Date): string {
    const opts: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' };
    return `${new Date(start).toLocaleDateString('en-US', opts)} – ${new Date(end).toLocaleDateString('en-US', opts)}`;
  }

  formatMatchDate(date: Date): string {
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const matchDate = new Date(date);
    if (matchDate.toDateString() === today.toDateString()) return 'Today';
    if (matchDate.toDateString() === tomorrow.toDateString()) return 'Tomorrow';
    return matchDate.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  }

  getTeammates(match: any): string {
    const myId = this.playerService.getCurrentPlayerId();
    return match.players
      .filter((p: any) => match.myTeamPlayerIds.includes(p.id) && p.id !== myId)
      .map((p: any) => p.name)
      .join(', ');
  }

  getOpponents(match: any): string {
    return match.players
      .filter((p: any) => match.opponentTeamPlayerIds.includes(p.id))
      .map((p: any) => p.name)
      .join(', ');
  }

  constructor() {
    effect(() => {
      // No localStorage during SSR, so currentUser is always null on the
      // server - skip the redirect there and let it re-run for real once the
      // client boots and AuthService has restored the actual session.
      if (!isPlatformBrowser(this.platformId)) {
        return;
      }

      const user = this.authService.currentUser();
      if (!user) {
        this.router.navigate(['/login']);
      } else {
        this.groupsService.loadGroupsForCurrentUser();
        this.matchService.loadMatchesForPlayer(user.email);
        // Prefill the distance search with where this player lives, so they can see
        // and override the origin. Present already if they just signed up; signing
        // in rebuilds the cached user from a response that carries no ZIP (and
        // widening that response would expose every player's ZIP via /players),
        // so fall back to the profile.
        //
        // Guarded by a plain flag, NOT by reading searchZip(): reading the signal
        // here would make this effect depend on it, so writing it below would
        // re-run the effect and re-issue the group/match loads above.
        if (!this.zipLookedUp) {
          this.zipLookedUp = true;
          const cached = user.zip_code ?? '';
          if (cached) {
            this.searchZip.set(cached);
          } else {
            this.authService.getProfile().subscribe({
              next: (profile) => this.searchZip.set(profile.zip_code ?? ''),
              error: () => { /* Not fatal: they can type a ZIP, or omit the radius. */ },
            });
          }
        }
      }
    });

    this.generateLastLoginTimestamp();
    this.playerService.fetchAllLeagues();
  }

  // Upcoming events across all groups the player belongs to
  upcomingEvents = computed<UpcomingGroupEvent[]>(() => {
    const now = new Date();
    const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    const items: UpcomingGroupEvent[] = [];
    for (const group of this.groupsService.groups()) {
      for (const event of group.events ?? []) {
        if (event.date >= todayStr) {
          items.push({ groupId: group.group_id, groupName: group.name, event });
        }
      }
    }
    items.sort((a, b) =>
      (a.event.date + (a.event.time ?? '')).localeCompare(b.event.date + (b.event.time ?? '')));
    return items.slice(0, 4);
  });

  eventDay(dateStr: string): string {
    return dateStr.split('-')[2] ?? '';
  }

  eventMonth(dateStr: string): string {
    const m = Number(dateStr.split('-')[1]);
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return months[m - 1] ?? '';
  }

  formatEventDate(dateStr: string): string {
    const [y, m, d] = dateStr.split('-').map(Number);
    if (!y || !m || !d) return dateStr;
    return this.formatMatchDate(new Date(y, m - 1, d));
  }

  formatEventTime(time: string): string {
    const [h, m] = time.split(':').map(Number);
    if (isNaN(h) || isNaN(m)) return time;
    const suffix = h >= 12 ? 'PM' : 'AM';
    const hour12 = h % 12 === 0 ? 12 : h % 12;
    return `${hour12}:${String(m).padStart(2, '0')} ${suffix}`;
  }

  inCount(event: GroupEvent): number {
    return (event.votes ?? []).filter(v => v.vote === 'In').length;
  }

  private generateLastLoginTimestamp() {
    const now = new Date();
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    yesterday.setHours(22, 52, 0);

    const day = String(yesterday.getDate()).padStart(2, '0');
    const month = String(yesterday.getMonth() + 1).padStart(2, '0');
    const year = String(yesterday.getFullYear()).substring(2);

    this.welcomeTimestamp = `${day}/${month}/${year}, 10:52 PM`;
  }

  searchPlayers(): void {
    const first = this.searchFirstName.trim();
    const last = this.searchLastName.trim();
    const radius = this.searchRadiusMiles;
    const zip = this.searchZip().trim();

    // Every filter blank would just dump the whole roster.
    if (!first && !last && this.searchDuprMin == null && this.searchDuprMax == null
      && radius == null) {
      return;
    }

    // The template renders duprRangeInvalid directly, so it appears as soon as the
    // range goes bad and clears the moment it's fixed - don't mirror it into
    // searchError, which would linger until the next submit. The backend enforces
    // this too; skipping the request just saves a round-trip.
    if (this.duprRangeInvalid) return;

    let params = new HttpParams();
    if (first) params = params.set('first_name', first);
    if (last) params = params.set('last_name', last);
    if (this.searchDuprMin != null) params = params.set('dupr_min', this.searchDuprMin);
    if (this.searchDuprMax != null) params = params.set('dupr_max', this.searchDuprMax);
    if (radius != null) params = params.set('radius_miles', radius);
    // Only meaningful alongside a radius, and only when they typed one.
    if (radius != null && zip) params = params.set('origin_zip', zip);

    this.isSearching.set(true);
    this.searchError.set(null);
    this.zipError.set(null);
    this.hasSearched.set(true);

    this.http.get<PlayerSearchResponse>('api/v1/players/search', { params }).subscribe({
      next: (resp) => {
        this.searchResults.set(resp.results ?? []);
        this.appliedRadius.set(resp.radius_miles ?? null);
        // Show which ZIP the distances were measured from, including when it came
        // from their profile rather than the box.
        if (resp.origin_zip && !zip) this.searchZip.set(resp.origin_zip);
        this.isSearching.set(false);
      },
      error: (err) => {
        const detail = err?.error?.detail;
        const code = detail?.code;
        const message = detail?.message;
        this.searchResults.set([]);
        this.appliedRadius.set(null);
        if (code === 'origin_zip_missing' || code === 'origin_zip_unknown') {
          this.zipError.set(message ?? 'Enter a ZIP code to search by distance.');
        } else {
          this.searchError.set(message ?? 'Unable to search players. Please try again.');
        }
        this.isSearching.set(false);
      }
    });
  }

  clearSearch(): void {
    this.searchFirstName = '';
    this.searchLastName = '';
    this.searchDuprMin = null;
    this.searchDuprMax = null;
    this.searchRadiusMiles = null;
    // The ZIP is kept: it's where this player lives, not part of the query.
    this.searchResults.set([]);
    this.appliedRadius.set(null);
    this.hasSearched.set(false);
    this.searchError.set(null);
    this.zipError.set(null);
  }
}
