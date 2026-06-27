import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MatchDetailComponent } from './match-detail';
import { ActivatedRoute } from '@angular/router';
import { PlayerService } from './player';
import { of } from 'rxjs';

describe('MatchDetailComponent', () => {
    let component: MatchDetailComponent;
    let fixture: ComponentFixture<MatchDetailComponent>;
    let mockPlayerService: any;
    let mockActivatedRoute: any;

    beforeEach(async () => {
        mockPlayerService = {
            getCurrentPlayerId: () => 'test-user',
            getMatchById: () => ({
                id: '1',
                status: 'completed',
                leagueName: 'Test League',
                date: new Date(),
                time: '12:00',
                court: '1',
                players: [],
                myTeamPlayerIds: [],
                opponentTeamPlayerIds: [],
                team1Score: 11,
                team2Score: 9
            }),
            updateMatchScore: () => of(true)
        };

        mockActivatedRoute = {
            snapshot: {
                paramMap: {
                    get: () => '1'
                }
            }
        };

        await TestBed.configureTestingModule({
            imports: [MatchDetailComponent],
            providers: [
                { provide: PlayerService, useValue: mockPlayerService },
                { provide: ActivatedRoute, useValue: mockActivatedRoute }
            ]
        })
            .compileComponents();

        fixture = TestBed.createComponent(MatchDetailComponent);
        component = fixture.componentInstance;
        fixture.detectChanges();
    });

    it('should create', () => {
        expect(component).toBeTruthy();
    });

    it('should validate scores before submission', () => {
        spyOn(window, 'alert');
        component.match.set({ id: '1', leagueId: 'L1', players: [] } as any);

        // Test negative
        component.team1Score.set(-1);
        component.team2Score.set(5);
        component.submitScore();
        expect(window.alert).toHaveBeenCalledWith('Please enter valid positive integer scores for both teams.');

        // Test decimal
        component.team1Score.set(5.5);
        component.team2Score.set(5);
        component.submitScore();
        expect(window.alert).toHaveBeenCalledWith('Please enter valid positive integer scores for both teams.');
    });

    it('should show edit button for ANY user on completed match', () => {
        // Trigger generic change detection
        fixture.detectChanges();

        const compiled = fixture.nativeElement as HTMLElement;
        const buttons = Array.from(compiled.querySelectorAll('button'));
        const hasEditBtn = buttons.some(b => b.textContent?.includes('Edit Score'));

        // Should be true now for everyone
        expect(hasEditBtn).toBe(true);
    });
});
