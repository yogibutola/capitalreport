import { Component, signal, inject, effect, PLATFORM_ID } from '@angular/core';
import { RouterOutlet, Router, RouterLink, RouterLinkActive, NavigationEnd } from '@angular/router';
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
  protected playerService = inject(PlayerService);

  protected readonly title = signal('DinkLeague');
  currentUser = this.authService.currentUser;
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

  constructor() {
    // Apply theme to document root
    effect(() => {
      if (isPlatformBrowser(this.platformId)) {
        document.documentElement.setAttribute('data-theme', this.currentTheme());
      }
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
