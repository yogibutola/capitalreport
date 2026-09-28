/**
 * The paddle bag a player can put on their profile.
 *
 * The brand list is a frontend-only input affordance: the backend validates the
 * *length* of a brand, never its membership, so there is nothing for it to do
 * with this list and no endpoint to keep in sync. If a "filter by brand" search
 * facet is ever added, that's the moment to promote the list to the backend —
 * a facet needs canonical server-side values.
 */
export const PADDLE_BRANDS = [
  'Joola',
  'Selkirk',
  'CRBN',
  'Paddletek',
  'Engage',
  'Six Zero',
  'Vatic Pro',
  'Ronbus',
  'Gearbox',
  'Franklin',
  'ProKennex',
  'Head',
  'Onix',
] as const;

/** Sentinel for "my brand isn't listed"; rendered last, never inside PADDLE_BRANDS. */
export const OTHER_BRAND = 'Other';

/** Must match MAX_PADDLES in app/vo/pb/player.py. */
export const MAX_PADDLES = 3;

export interface Paddle {
  brand: string;
  model?: string | null;
}
