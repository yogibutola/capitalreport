import { Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule, NgForm } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../auth/auth';
import { BrandMarkComponent } from '../shared/brand-mark';
import { FORM_ERROR_UI, ParsedHttpError } from '../shared/form-error-ui';
import { PlatformPlayer, PlatformClub, PlatformService } from './platform.service';

type Tab = 'clubs' | 'players' | 'activity';

@Component({
    selector: 'app-platform-console',
    standalone: true,
    imports: [FormsModule, DatePipe, ...FORM_ERROR_UI, BrandMarkComponent],
    templateUrl: './platform-console.html',
    styleUrl: './platform-console.css',
})
export class PlatformConsoleComponent implements OnInit {
    svc = inject(PlatformService);
    private auth = inject(AuthService);
    private router = inject(Router);

    tab = signal<Tab>('clubs');

    // add-club form
    showClubForm = signal(false);
    club = { firstName: '', lastName: '', clubName: '', email: '', password: '', address: '', phone: '' };
    clubBusy = signal(false);
    clubAttempted = signal(false);
    clubFormError = signal<string | null>(null);
    clubFieldErrors = signal<Record<string, string>>({});

    // add-player form
    showPlayerForm = signal(false);
    player = { firstName: '', lastName: '', email: '', password: '', dupr_rating: 3.0 };
    playerBusy = signal(false);
    playerAttempted = signal(false);
    playerFormError = signal<string | null>(null);
    playerFieldErrors = signal<Record<string, string>>({});

    // activity filter
    activityActor = '';

    ngOnInit() {
        this.svc.refreshAll();
    }

    setTab(t: Tab) {
        this.tab.set(t);
    }

    logout() {
        this.auth.logout();
        this.router.navigate(['/x9k2-console/login']);
    }

    // ---- clubs -------------------------------------------------------------

    submitClub(form: NgForm) {
        this.clubAttempted.set(true);
        this.clubFormError.set(null);
        this.clubFieldErrors.set({});
        if (this.clubBusy() || form.invalid) return;

        this.clubBusy.set(true);
        this.svc
            .addClub({
                firstName: this.club.firstName.trim(),
                lastName: this.club.lastName.trim(),
                clubName: this.club.clubName.trim(),
                email: this.club.email.trim(),
                password: this.club.password,
                address: this.club.address.trim() || undefined,
                phone: this.club.phone.trim() || undefined,
            })
            .subscribe({
                next: () => {
                    this.clubBusy.set(false);
                    this.showClubForm.set(false);
                    this.clubAttempted.set(false);
                    this.club = { firstName: '', lastName: '', clubName: '', email: '', password: '', address: '', phone: '' };
                },
                error: (err: ParsedHttpError) => {
                    this.clubBusy.set(false);
                    this.clubFieldErrors.set({ ...err.fieldErrors });
                    this.clubFormError.set(Object.keys(err.fieldErrors).length ? null : err.message);
                },
            });
    }

    removeClub(c: PlatformClub) {
        this.svc.removeClub(c);
    }

    // ---- players ---------------------------------------------------------

    submitPlayer(form: NgForm) {
        this.playerAttempted.set(true);
        this.playerFormError.set(null);
        this.playerFieldErrors.set({});
        if (this.playerBusy() || form.invalid) return;

        this.playerBusy.set(true);
        this.svc
            .addPlayer({
                firstName: this.player.firstName.trim(),
                lastName: this.player.lastName.trim(),
                email: this.player.email.trim(),
                password: this.player.password,
                dupr_rating: Number(this.player.dupr_rating),
            })
            .subscribe({
                next: () => {
                    this.playerBusy.set(false);
                    this.showPlayerForm.set(false);
                    this.playerAttempted.set(false);
                    this.player = { firstName: '', lastName: '', email: '', password: '', dupr_rating: 3.0 };
                },
                error: (err: ParsedHttpError) => {
                    this.playerBusy.set(false);
                    this.playerFieldErrors.set({ ...err.fieldErrors });
                    this.playerFormError.set(Object.keys(err.fieldErrors).length ? null : err.message);
                },
            });
    }

    removePlayer(p: PlatformPlayer) {
        this.svc.removePlayer(p);
    }

    // ---- activity ------------------------------------------------------

    viewActivityFor(actor: string) {
        this.activityActor = actor;
        this.tab.set('activity');
        this.svc.fetchActivity({ actor });
    }

    applyActivityFilter() {
        this.svc.fetchActivity(this.activityActor.trim() ? { actor: this.activityActor.trim() } : {});
    }

    clearActivityFilter() {
        this.activityActor = '';
        this.svc.fetchActivity();
    }
}
