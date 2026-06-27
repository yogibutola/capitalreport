import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { PlayerService, UpcomingMatch } from './player';

@Component({
    selector: 'app-match-detail',
    standalone: true,
    imports: [CommonModule, FormsModule],
    templateUrl: './match-detail.html',
    styleUrl: './match-detail.css'
})
export class MatchDetailComponent implements OnInit {
    route = inject(ActivatedRoute);
    router = inject(Router);
    playerService = inject(PlayerService);

    match = signal<UpcomingMatch | undefined>(undefined);
    currentPlayerId = this.playerService.getCurrentPlayerId();

    // Score entry state
    isScoring = signal(false);
    team1Score = signal<number | null>(null); // My Team
    team2Score = signal<number | null>(null); // Opponent Team

    ngOnInit() {
        this.loadMatchData();
    }

    private loadMatchData() {
        const matchId = this.route.snapshot.paramMap.get('id');
        if (matchId) {
            const foundMatch = this.playerService.getMatchById(matchId);
            this.match.set(foundMatch);
            if (foundMatch) {
                this.team1Score.set(foundMatch.team1Score ?? null);
                this.team2Score.set(foundMatch.team2Score ?? null);
            }
        }
    }

    goBack() {
        this.router.navigate(['/player']);
    }

    formatDate(date: Date): string {
        return new Date(date).toLocaleDateString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    }

    getMyTeamPlayers() {
        const m = this.match();
        if (!m) return [];
        return m.players.filter(p => m.myTeamPlayerIds.includes(p.id));
    }

    getOpponentTeamPlayers() {
        const m = this.match();
        if (!m) return [];
        return m.players.filter(p => m.opponentTeamPlayerIds.includes(p.id));
    }

    toggleScoreEntry() {
        this.isScoring.update(v => !v);
    }

    // Prevent non-integer input
    preventNonIntegerInput(event: KeyboardEvent) {
        // Allow: Backspace, Delete, Tab, Escape, Enter
        if ([46, 8, 9, 27, 13].indexOf(event.keyCode) !== -1 ||
            // Allow: Ctrl+A
            (event.keyCode === 65 && (event.ctrlKey || event.metaKey)) ||
            // Allow: Ctrl+C
            (event.keyCode === 67 && (event.ctrlKey || event.metaKey)) ||
            // Allow: Ctrl+V
            (event.keyCode === 86 && (event.ctrlKey || event.metaKey)) ||
            // Allow: Ctrl+X
            (event.keyCode === 88 && (event.ctrlKey || event.metaKey)) ||
            // Allow: home, end, left, right
            (event.keyCode >= 35 && event.keyCode <= 39)) {
            // let it happen, don't do anything
            return;
        }
        // Ensure that it is a number and stop the keypress
        if ((event.shiftKey || (event.keyCode < 48 || event.keyCode > 57)) && (event.keyCode < 96 || event.keyCode > 105)) {
            event.preventDefault();
        }
    }

    submitScore() {
        const t1 = this.team1Score();
        const t2 = this.team2Score();
        const m = this.match();
        const matchId = m?.id;

        if (t1 === null || t2 === null || !matchId || !m ||
            !Number.isInteger(t1) || t1 < 0 ||
            !Number.isInteger(t2) || t2 < 0) {
            console.log('Please enter valid positive integer scores for both teams.');
            return;
        }

        console.log(`Submitting score for match ${matchId} in league ${m.leagueId}: ${t1} - ${t2}`);

        this.playerService.updateMatchScore(m.leagueId, matchId, t1, t2, m.myTeamName, m.opponentTeamName).subscribe(success => {
            if (success) {
                this.isScoring.set(false);
                console.log('Score submitted successfully!');

                // Update local match state if possible
                const currentMatch = this.match();
                if (currentMatch) {
                    currentMatch.status = 'completed';
                    currentMatch.team1Score = t1;
                    currentMatch.team2Score = t2;
                    this.match.set({ ...currentMatch });
                }
            } else {
                console.log('Failed to submit score. Please try again.');
            }
        });
    }
}
