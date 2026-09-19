import { Component, inject, NgZone, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule, NgForm } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { catchError, finalize, throwError } from 'rxjs';
import { FORM_ERROR_UI, parseHttpError, ParsedHttpError } from '../shared/form-error-ui';
import { BrandLogoComponent } from '../shared/brand-logo';
import { BrandMarkComponent } from '../shared/brand-mark';
import { ThemeToggleComponent } from '../shared/theme-toggle';

export interface DemoRequestPayload {
    name: string;
    email: string;
    club_name: string;
    phone?: string;
    club_size?: string;
    preferred_time?: string;
    message?: string;
}

export interface DemoRequestResponse {
    request_id: string;
    message: string;
}

const CLUB_SIZES = ['Under 50 players', '50–150 players', '150–400 players', '400+ players'];

const AGENDA = [
    { title: 'Your league, live', body: 'We import your roster and build a real season on the call.' },
    { title: 'Smart Slotting walk-through', body: 'Watch a round get scheduled, scored and re-slotted in minutes.' },
    { title: 'Ratings & tournaments', body: 'DUPR tracking, brackets and public registration, end to end.' },
    { title: 'Pricing & rollout', body: 'A plan sized to your club and a launch checklist you can keep.' },
];

@Component({
    selector: 'app-book-demo',
    standalone: true,
    imports: [FormsModule, RouterLink, ...FORM_ERROR_UI, BrandLogoComponent, BrandMarkComponent, ThemeToggleComponent],
    templateUrl: './book-demo.html',
    styleUrl: './book-demo.css'
})
export class BookDemoComponent {
    private http = inject(HttpClient);
    private zone = inject(NgZone);

    readonly clubSizes = CLUB_SIZES;
    readonly agenda = AGENDA;
    readonly fieldLabels = {
        name: 'Your name',
        email: 'Work email',
        clubName: 'Club name',
        phone: 'Phone',
        clubSize: 'Club size',
        preferredTime: 'Preferred time',
        message: 'Anything else',
    };

    model = {
        name: '',
        email: '',
        clubName: '',
        phone: '',
        clubSize: '',
        preferredTime: '',
        message: '',
    };

    isSubmitting = signal(false);
    submitAttempted = signal(false);
    submitted = signal<DemoRequestResponse | null>(null);
    formError = signal<string | null>(null);
    fieldErrors = signal<Record<string, string>>({});

    clearServerErrors() {
        this.formError.set(null);
        this.fieldErrors.set({});
    }

    onSubmit(form: NgForm) {
        this.submitAttempted.set(true);
        this.clearServerErrors();
        if (this.isSubmitting() || form.invalid) return;

        const payload: DemoRequestPayload = {
            name: this.model.name.trim(),
            email: this.model.email.trim(),
            club_name: this.model.clubName.trim(),
            phone: this.model.phone.trim() || undefined,
            club_size: this.model.clubSize || undefined,
            preferred_time: this.model.preferredTime.trim() || undefined,
            message: this.model.message.trim() || undefined,
        };

        this.isSubmitting.set(true);
        this.http.post<DemoRequestResponse>('api/v1/book-demo', payload).pipe(
            catchError((err) => throwError(() => parseHttpError(err))),
            finalize(() => this.zone.run(() => this.isSubmitting.set(false)))
        ).subscribe({
            next: (res) => this.zone.run(() => this.submitted.set(res)),
            error: (err: ParsedHttpError) => {
                this.zone.run(() => {
                    // Backend field names are snake_case; map them onto the form controls.
                    const raw = err.fieldErrors ?? {};
                    const mapped: Record<string, string> = {};
                    for (const [key, msg] of Object.entries(raw)) {
                        mapped[this.toControlName(key)] = msg;
                    }
                    this.fieldErrors.set(mapped);
                    this.formError.set(Object.keys(mapped).length ? null : err.message);
                });
            }
        });
    }

    private toControlName(apiField: string): string {
        return apiField.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
    }
}
