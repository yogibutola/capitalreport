import { ComponentFixture, TestBed } from '@angular/core/testing';

import { MatchEntryComponent } from './match-entry';

describe('MatchEntryComponent', () => {
  let component: MatchEntryComponent;
  let fixture: ComponentFixture<MatchEntryComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MatchEntryComponent]
    })
      .compileComponents();

    fixture = TestBed.createComponent(MatchEntryComponent);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should invalidate form with negative scores', () => {
    component.partnerId = '1';
    component.opponent1Id = '2';
    component.opponent2Id = '3';
    component.myScore = -1;
    component.opponentScore = 5;
    expect(component.isFormValid()).toBe(false);
  });

  it('should invalidate form with non-integer scores', () => {
    component.partnerId = '1';
    component.opponent1Id = '2';
    component.opponent2Id = '3';
    component.myScore = 5.5;
    component.opponentScore = 5;
    expect(component.isFormValid()).toBe(false);
  });

  it('should validate form with valid positive integers', () => {
    component.partnerId = '1';
    component.opponent1Id = '2';
    component.opponent2Id = '3';
    component.myScore = 11;
    component.opponentScore = 9;
    expect(component.isFormValid()).toBe(true);
  });
});
