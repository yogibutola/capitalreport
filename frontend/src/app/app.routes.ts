import { Routes } from '@angular/router';
import { LoginComponent } from './auth/login';
import { SignupComponent } from './auth/signup';
import { DashboardComponent } from './league/dashboard';
import { DailySlottingComponent } from './league/daily-slotting';
import { MatchEntryComponent } from './matches/match-entry';
import { MatchHistoryComponent } from './matches/match-history';
import { ProfileComponent } from './stats/profile';
import { DashboardComponent as AdminDashboardComponent } from './admin/dashboard';
import { CreateLeagueComponent } from './admin/create-league';
import { PlayerDashboardComponent } from './player/player-dashboard';
import { PlayerLeaguesComponent } from './player/player-leagues';
import { MatchDetailComponent } from './player/match-detail';
import { LeagueDetailsComponent } from './admin/league-details';
import { AdminLoginComponent } from './admin/admin-login';
import { ClubSignupComponent } from './admin/club-signup';
import { HomeComponent } from './home/home';
import { adminGuard } from './auth/admin.guard';

export const routes: Routes = [
    { path: 'admin', component: AdminDashboardComponent, canActivate: [adminGuard] },
    { path: 'admin/login', component: AdminLoginComponent },
    { path: 'admin/signup', component: ClubSignupComponent },
    { path: 'admin/create-league', component: CreateLeagueComponent, canActivate: [adminGuard] },
    { path: 'admin/league/:league_id', component: LeagueDetailsComponent, canActivate: [adminGuard] },
    { path: 'login', component: LoginComponent },
    { path: 'signup', component: SignupComponent },
    { path: 'player', component: PlayerDashboardComponent },
    { path: 'player/leagues', component: PlayerLeaguesComponent },
    { path: 'player/match/:id', component: MatchDetailComponent },
    { path: 'league', component: DashboardComponent },
    { path: 'league/slotting', component: DailySlottingComponent },
    { path: 'matches/entry', component: MatchEntryComponent },
    { path: 'matches/history', component: MatchHistoryComponent },
    { path: 'profile', component: ProfileComponent },
    { path: '', component: HomeComponent }
];
