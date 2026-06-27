import { RenderMode, ServerRoute } from '@angular/ssr';

export const serverRoutes: ServerRoute[] = [
  {
    path: 'player/match/:id',
    renderMode: RenderMode.Server,
  },
  // Default to Server Side Rendering for all routes to avoid build-time prerendering failures
  {
    path: '**',
    renderMode: RenderMode.Server,
  },
];
