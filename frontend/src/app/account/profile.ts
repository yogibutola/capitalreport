import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService, Profile } from '../auth/auth';
import { ToastService } from '../shared/toast.service';
import { FORM_ERROR_UI, ParsedHttpError } from '../shared/form-error-ui';

interface ProfileFields {
  firstName: string;
  lastName: string;
  email: string;
  age: number | null;
  dupr_rating: number | null;
  state: string;
  city: string;
  clubName: string;
  address: string;
  phone: string;
}

@Component({
  selector: 'app-account-profile',
  standalone: true,
  imports: [FormsModule, RouterLink, ...FORM_ERROR_UI],
  templateUrl: './profile.html',
  styleUrl: './profile.css',
})
export class AccountProfileComponent implements OnInit {
  private auth = inject(AuthService);
  private toast = inject(ToastService);

  // ---- Profile form ----
  firstName = '';
  lastName = '';
  email = '';
  age: number | null = null;
  dupr_rating: number | null = null;
  state = '';
  city = '';
  // Club (admin) accounts
  clubName = '';
  address = '';
  phone = '';

  role = signal<'player' | 'admin'>(this.auth.currentUser()?.role ?? 'player');
  isClub = computed(() => this.role() === 'admin');

  loading = signal(true);
  editing = signal(false);
  savingProfile = signal(false);
  profileAttempted = signal(false);
  profileError = signal<string | null>(null);
  profileFieldErrors = signal<Record<string, string>>({});

  /** Last known-good values, used to restore the form when an edit is cancelled. */
  private saved: ProfileFields = this.snapshot();

  // ---- Change-password form ----
  passwordOpen = signal(false);
  currentPassword = '';
  newPassword = '';
  confirmPassword = '';
  passwordFocus = false;

  savingPassword = signal(false);
  passwordAttempted = signal(false);
  passwordError = signal<string | null>(null);
  passwordFieldErrors = signal<Record<string, string>>({});

  ngOnInit(): void {
    // Show cached values instantly, then reconcile with the server.
    this.hydrate(this.auth.currentUser());
    this.auth.getProfile().subscribe({
      next: (p) => {
        this.hydrate(p);
        this.loading.set(false);
      },
      error: (err: ParsedHttpError) => {
        this.loading.set(false);
        this.profileError.set(err.message);
      },
    });
  }

  private hydrate(source: Partial<Profile> | { firstName?: string } | null | undefined): void {
    if (!source) return;
    const p = source as Partial<Profile>;
    if (p.role) this.role.set(p.role);
    this.firstName = p.firstName ?? this.firstName;
    this.lastName = p.lastName ?? this.lastName;
    this.email = p.email ?? this.email;
    this.age = p.age ?? this.age ?? null;
    this.dupr_rating = p.dupr_rating ?? this.dupr_rating ?? null;
    this.state = p.state ?? this.state;
    this.city = p.city ?? this.city;
    this.clubName = p.clubName ?? this.clubName;
    this.address = p.address ?? this.address;
    this.phone = p.phone ?? this.phone;
    this.saved = this.snapshot();
  }

  private snapshot(): ProfileFields {
    return {
      firstName: this.firstName,
      lastName: this.lastName,
      email: this.email,
      age: this.age,
      dupr_rating: this.dupr_rating,
      state: this.state,
      city: this.city,
      clubName: this.clubName,
      address: this.address,
      phone: this.phone,
    };
  }

  private restore(): void {
    Object.assign(this, this.saved);
  }

  // ---- Edit mode ----
  startEdit(): void {
    this.clearProfileErrors();
    this.profileAttempted.set(false);
    this.editing.set(true);
  }

  cancelEdit(): void {
    this.restore();
    this.clearProfileErrors();
    this.profileAttempted.set(false);
    this.editing.set(false);
  }

  // ---- Change-password panel ----
  togglePassword(): void {
    const next = !this.passwordOpen();
    this.passwordOpen.set(next);
    if (!next) this.resetPasswordForm();
  }

  private resetPasswordForm(form?: NgForm): void {
    this.currentPassword = '';
    this.newPassword = '';
    this.confirmPassword = '';
    this.passwordAttempted.set(false);
    this.clearPasswordErrors();
    form?.resetForm();
  }

  // Password strength checklist (mirrors the backend complexity rules).
  get hasMinLength() { return this.newPassword.length >= 8; }
  get hasUpperCase() { return /[A-Z]/.test(this.newPassword); }
  get hasNumber() { return /[0-9]/.test(this.newPassword); }
  get hasSpecialChar() { return /[@#$]/.test(this.newPassword); }
  get isNewPasswordValid() {
    return this.hasMinLength && this.hasUpperCase && this.hasNumber && this.hasSpecialChar;
  }
  get passwordsMatch() {
    return this.confirmPassword.length > 0 && this.newPassword === this.confirmPassword;
  }

  clearProfileErrors(): void {
    this.profileError.set(null);
    this.profileFieldErrors.set({});
  }

  clearPasswordErrors(): void {
    this.passwordError.set(null);
    this.passwordFieldErrors.set({});
  }

  saveProfile(form: NgForm): void {
    this.profileAttempted.set(true);
    this.clearProfileErrors();
    if (this.savingProfile() || form.invalid) return;

    const payload = this.isClub()
      ? {
          clubName: this.clubName.trim(),
          email: this.email.trim(),
          address: this.address.trim(),
          phone: this.phone.trim(),
        }
      : {
          firstName: this.firstName.trim(),
          lastName: this.lastName.trim(),
          email: this.email.trim(),
          age: this.age === null || this.age === undefined ? null : Number(this.age),
          dupr_rating:
            this.dupr_rating === null || this.dupr_rating === undefined
              ? null
              : Number(this.dupr_rating),
          state: this.state.trim(),
          city: this.city.trim(),
        };

    this.savingProfile.set(true);
    this.auth.updateProfile(payload).subscribe({
      next: (profile) => {
        this.savingProfile.set(false);
        this.profileAttempted.set(false);
        this.hydrate(profile);
        this.editing.set(false);
        this.toast.success(this.isClub() ? 'Club profile updated.' : 'Profile updated.');
      },
      error: (err: ParsedHttpError) => {
        this.savingProfile.set(false);
        this.profileFieldErrors.set({ ...err.fieldErrors });
        this.profileError.set(
          Object.keys(err.fieldErrors).length
            ? 'Please correct the highlighted fields and try again.'
            : err.message
        );
      },
    });
  }

  changePassword(form: NgForm): void {
    this.passwordAttempted.set(true);
    this.clearPasswordErrors();
    if (
      this.savingPassword() ||
      form.invalid ||
      !this.isNewPasswordValid ||
      !this.passwordsMatch
    ) {
      return;
    }

    this.savingPassword.set(true);
    this.auth.changePassword(this.currentPassword, this.newPassword).subscribe({
      next: () => {
        this.savingPassword.set(false);
        this.resetPasswordForm(form);
        this.passwordOpen.set(false);
        this.toast.success('Password changed.');
      },
      error: (err: ParsedHttpError) => {
        this.savingPassword.set(false);
        this.passwordFieldErrors.set({ ...err.fieldErrors });
        this.passwordError.set(
          Object.keys(err.fieldErrors).length
            ? 'Please correct the highlighted fields and try again.'
            : err.message
        );
      },
    });
  }
}
