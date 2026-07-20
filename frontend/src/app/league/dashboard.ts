import { Component, computed, effect, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe, CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { AuthService } from '../auth/auth';
import { PlayerService } from '../player/player';
import { FormsModule } from '@angular/forms';
import { GroupsService, GroupEvent } from '../groups/groups.service';

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
    dupr_rating: number;
    role: string;
    leagues: { league_name: string }[];
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterLink, CommonModule, FormsModule],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css'
})
export class DashboardComponent {
  private authService = inject(AuthService);
  private router = inject(Router);
  private http = inject(HttpClient);
  private groupsService = inject(GroupsService);
  protected playerService = inject(PlayerService);

  currentUser = this.authService.currentUser;
  leagues = this.playerService.getLeagues;
  upcomingMatches = this.playerService.getUpcomingMatches;
  completedMatches = this.playerService.getCompletedMatches;
  availableLeagues = this.playerService.getAvailableLeagues;

  // Premium banking visual states
  welcomeTimestamp = '';

  // Player search
  searchFirstName = '';
  searchLastName = '';
  searchResults = signal<PlayerResult[]>([]);
  private allPlayers = signal<PlayerResult[]>([]);
  isSearching = signal(false);
  searchError = signal<string | null>(null);
  hasSearched = signal(false);

  get nextMatch() {
    const matches = this.upcomingMatches();
    if (!matches.length) return null;
    return [...matches].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())[0];
  }

  get latestAvailableLeague() {
    return this.availableLeagues()[0] ?? null;
  }

  // Last 5 completed games as W/L, oldest → most recent
  get lastFiveResults(): ('W' | 'L')[] {
    return [...this.completedMatches()]
      .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
      .slice(0, 5)
      .reverse()
      .map(m => (m.team1Score || 0) > (m.team2Score || 0) ? 'W' : 'L');
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
      if (!this.authService.currentUser()) {
        this.router.navigate(['/login']);
      } else {
        this.groupsService.loadGroupsForCurrentUser();
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
    const first = this.searchFirstName.trim().toLowerCase();
    const last = this.searchLastName.trim().toLowerCase();
    if (!first && !last) return;

    this.isSearching.set(true);
    this.searchError.set(null);
    this.hasSearched.set(true);

    if (this.allPlayers().length > 0) {
      this.filterPlayers(first, last);
      this.isSearching.set(false);
      return;
    }

    this.http.get<PlayerResult[]>('api/v1/players').subscribe({
      next: (players) => {
        this.allPlayers.set(players);
        this.filterPlayers(first, last);
        this.isSearching.set(false);
      },
      error: () => {
        this.searchError.set('Unable to fetch players. Please try again.');
        this.isSearching.set(false);
      }
    });
  }

  private filterPlayers(first: string, last: string): void {
    const filtered = this.allPlayers().filter(p => {
      const firstMatch = !first || p.firstName.toLowerCase().includes(first);
      const lastMatch = !last || p.lastName.toLowerCase().includes(last);
      return firstMatch && lastMatch;
    });
    this.searchResults.set(filtered);
  }

  clearSearch(): void {
    this.searchFirstName = '';
    this.searchLastName = '';
    this.searchResults.set([]);
    this.hasSearched.set(false);
    this.searchError.set(null);
  }
}
