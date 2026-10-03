import { Routes } from '@angular/router';
import { LoginComponent } from './auth/login';
import { SignupComponent } from './auth/signup';
import { ForgotPasswordComponent } from './auth/forgot-password';
import { ResetPasswordComponent } from './auth/reset-password';
import { DashboardComponent } from './league/dashboard';
import { DailySlottingComponent } from './league/daily-slotting';
import { MatchEntryComponent } from './matches/match-entry';
import { MatchHistoryComponent } from './matches/match-history';
import { ProfileComponent } from './stats/profile';
import { AccountProfileComponent } from './account/profile';
import { ActiveSeasonComponent } from './admin/active-season';
import { LeaguesComponent as AdminLeaguesComponent } from './admin/leagues';
import { TournamentsComponent as AdminTournamentsComponent } from './admin/tournaments';
import { CreateLeagueComponent } from './admin/create-league';
import { CreateTournamentComponent } from './admin/create-tournament';
import { TournamentDetailsComponent } from './admin/tournament-details';
import { PlayerDashboardComponent } from './player/player-dashboard';
import { PlayerLeaguesComponent } from './player/player-leagues';
import { PlayerTournamentsComponent } from './player/player-tournaments';
import { MatchDetailComponent } from './player/match-detail';
import { LeagueDetailsComponent } from './admin/league-details';
import { AdminLoginComponent } from './admin/admin-login';
import { ClubSignupComponent } from './admin/club-signup';
import { HomeComponent } from './home/home';
import { BookDemoComponent } from './home/book-demo';
import { TournamentRegisterComponent } from './tournament/tournament-register';
import { adminGuard } from './auth/admin.guard';
import { superAdminGuard } from './auth/super-admin.guard';
import { PlatformLoginComponent } from './platform/platform-login';
import { PlatformConsoleComponent } from './platform/platform-console';
import { MyGroupsComponent } from './groups/my-groups';

export const routes: Routes = [
    // The club hub ("Manage" tab) was removed; Leagues is the club landing page.
    { path: 'admin', redirectTo: 'admin/season', pathMatch: 'full' },
    { path: 'admin/leagues', component: AdminLeaguesComponent, canActivate: [adminGuard] },
    { path: 'admin/tournaments', component: AdminTournamentsComponent, canActivate: [adminGuard] },
    { path: 'admin/season', component: ActiveSeasonComponent, canActivate: [adminGuard] },
    { path: 'admin/login', component: AdminLoginComponent },
    { path: 'admin/signup', component: ClubSignupComponent },
    { path: 'admin/create-league', component: CreateLeagueComponent, canActivate: [adminGuard] },
    { path: 'admin/create-tournament', component: CreateTournamentComponent, canActivate: [adminGuard] },
    { path: 'admin/tournament/:tournament_id', component: TournamentDetailsComponent, canActivate: [adminGuard] },
    { path: 'admin/league/:league_id', component: LeagueDetailsComponent, canActivate: [adminGuard] },
    // Hidden application-admin console. Path is intentionally unadvertised and
    // not linked from any nav; superAdminGuard is the second line of defence.
    { path: 'x9k2-console/login', component: PlatformLoginComponent },
    { path: 'x9k2-console', component: PlatformConsoleComponent, canActivate: [superAdminGuard] },
    { path: 'login', component: LoginComponent },
    { path: 'signup', component: SignupComponent },
    { path: 'forgot-password', component: ForgotPasswordComponent },
    { path: 'reset-password', component: ResetPasswordComponent },
    { path: 'player', component: PlayerDashboardComponent },
    { path: 'player/leagues', component: PlayerLeaguesComponent },
    { path: 'player/tournaments', component: PlayerTournamentsComponent },
    { path: 'player/tournament/:tournament_id', component: TournamentDetailsComponent },
    { path: 'player/match/:id', component: MatchDetailComponent },
    { path: 'league', component: DashboardComponent },
    { path: 'league/slotting', component: DailySlottingComponent },
    { path: 'matches/entry', component: MatchEntryComponent },
    { path: 'matches/history', component: MatchHistoryComponent },
    { path: 'profile', component: AccountProfileComponent },
    { path: 'stats', component: ProfileComponent },
    { path: 'groups', component: MyGroupsComponent },
    { path: 'register-tournament/:tournament_id', component: TournamentRegisterComponent },
    { path: 'book-demo', component: BookDemoComponent },
    { path: '', component: HomeComponent }
];
