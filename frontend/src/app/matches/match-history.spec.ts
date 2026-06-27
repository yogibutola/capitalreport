import { ComponentFixture, TestBed } from '@angular/core/testing';

import { MatchHistory } from './match-history';

describe('MatchHistory', () => {
  let component: MatchHistory;
  let fixture: ComponentFixture<MatchHistory>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MatchHistory]
    })
    .compileComponents();

    fixture = TestBed.createComponent(MatchHistory);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
