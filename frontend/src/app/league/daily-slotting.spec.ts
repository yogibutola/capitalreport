import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DailySlottingComponent } from './daily-slotting';

describe('DailySlottingComponent', () => {
  let component: DailySlottingComponent;
  let fixture: ComponentFixture<DailySlottingComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DailySlottingComponent]
    })
      .compileComponents();

    fixture = TestBed.createComponent(DailySlottingComponent);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
