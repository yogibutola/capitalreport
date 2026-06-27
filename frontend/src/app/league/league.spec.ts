import { TestBed } from '@angular/core/testing';

import { League } from './league';

describe('League', () => {
  let service: League;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(League);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
