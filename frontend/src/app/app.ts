import { Component, signal, inject, effect, PLATFORM_ID } from '@angular/core';
import { RouterOutlet, Router, RouterLink, RouterLinkActive, NavigationEnd } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { AuthService } from './auth/auth';
import { ThemeService } from './theme.service';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { PlayerService } from './player/player';
import { toSignal } from '@angular/core/rxjs-interop';
import { filter, map } from 'rxjs/operators';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, CommonModule, RouterLink, RouterLinkActive],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  private authService = inject(AuthService);
  private themeService = inject(ThemeService);
  private router = inject(Router);
  private platformId = inject(PLATFORM_ID);
  private http = inject(HttpClient);
  protected playerService = inject(PlayerService);

  protected readonly title = signal('DinkLeague');
  currentUser = this.authService.currentUser;

  // AI-generated pickleball quote shown in the header, refreshed on each login.
  pickleballQuote = signal<string>('');
  currentTheme = this.themeService.theme;
  leagues = this.playerService.getLeagues;
  selectedLeague = this.playerService.getSelectedLeague;
  isLandingPage = toSignal(
    this.router.events.pipe(
      filter(e => e instanceof NavigationEnd),
      map((e: NavigationEnd) => e.urlAfterRedirects === '/')
    ),
    { initialValue: this.router.url === '/' }
  );

  private lastQuotedUser: string | null = null;

  constructor() {
    // Apply theme to document root
    effect(() => {
      if (isPlatformBrowser(this.platformId)) {
        document.documentElement.setAttribute('data-theme', this.currentTheme());
      }
    });

    // Fetch a fresh AI-generated pickleball quote whenever a user logs in.
    effect(() => {
      const user = this.currentUser();
      const userKey = user ? (user.email ?? `${user.firstName} ${user.lastName}`) : null;
      if (userKey && userKey !== this.lastQuotedUser) {
        this.lastQuotedUser = userKey;
        this.fetchPickleballQuote();
      } else if (!userKey) {
        this.lastQuotedUser = null;
        this.pickleballQuote.set('');
      }
    });
  }

  private fetchPickleballQuote() {
    this.http.get<{ quote: string }>('api/v1/pickleball/quote').subscribe({
      next: res => this.pickleballQuote.set(res.quote),
      error: () => this.pickleballQuote.set('')
    });
  }

  toggleTheme() {
    this.themeService.toggleTheme();
  }

  selectLeague(leagueId: string) {
    this.playerService.selectLeague(leagueId);
  }

  logout() {
    this.authService.logout();
    this.router.navigate(['/login']);
  }
}
