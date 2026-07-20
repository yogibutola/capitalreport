import { Injectable, signal, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { AuthService } from '../auth/auth';

export interface GroupMessage {
  message_id: string;
  author_email: string;
  author_name: string;
  content: string;
  timestamp: string;
}

export type VoteOption = 'In' | 'In but late' | 'In but leave early' | 'May be' | 'Out';

export const VOTE_OPTIONS: VoteOption[] = ['In', 'In but late', 'In but leave early', 'May be', 'Out'];

export interface EventVote {
  voter_email: string;
  voter_name: string;
  vote: VoteOption;
  timestamp: string;
}

export interface GroupEvent {
  event_id: string;
  title: string;
  date: string;
  time?: string;
  place?: string;
  notes?: string;
  votes: EventVote[];
  messages: GroupMessage[];
}

export interface EventDetails {
  title?: string;
  date?: string;
  time?: string;
  place?: string;
  notes?: string;
}

export interface Group {
  group_id: string;
  name: string;
  description?: string;
  creator_email: string;
  members: string[];
  events: GroupEvent[];
  messages: GroupMessage[];
  created_at: string;
}

export interface Player {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  dupr_rating: number;
}

@Injectable({ providedIn: 'root' })
export class GroupsService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);

  groups = signal<Group[]>([]);
  selectedGroup = signal<Group | null>(null);
  allPlayers = signal<Player[]>([]);
  isLoading = signal(false);

  // ─── Groups ───

  loadGroupsForCurrentUser() {
    const email = this.authService.currentUser()?.email;
    if (!email) return;
    this.isLoading.set(true);
    this.http.get<Group[]>(`api/v1/groups/player/${email.toLowerCase()}`).pipe(
      catchError(() => of([]))
    ).subscribe(groups => {
      this.groups.set(groups);
      this.isLoading.set(false);
    });
  }

  createGroup(name: string, description: string): Observable<Group | null> {
    const user = this.authService.currentUser();
    if (!user) return of(null);
    const payload = { name, description, creator_email: user.email };
    return this.http.post<Group>('api/v1/groups', payload).pipe(
      map(group => {
        this.groups.update(gs => [group, ...gs]);
        return group;
      }),
      catchError(() => of(null))
    );
  }

  selectGroup(groupId: string) {
    this.isLoading.set(true);
    this.http.get<Group>(`api/v1/groups/${groupId}`).pipe(
      catchError(() => of(null))
    ).subscribe(group => {
      this.selectedGroup.set(group);
      this.isLoading.set(false);
    });
  }

  // ─── Members ───

  addMember(groupId: string, email: string): Observable<boolean> {
    return this.http.post<any>(`api/v1/groups/${groupId}/members`, { email }).pipe(
      map(() => {
        // Refresh selected group
        this.selectGroup(groupId);
        return true;
      }),
      catchError(() => of(false))
    );
  }

  // ─── Events ───

  addEvent(groupId: string, details: EventDetails = {}): Observable<GroupEvent | null> {
    const payload: any = {};
    if (details.title) payload['title'] = details.title;
    if (details.date) payload['date'] = details.date;
    if (details.time) payload['time'] = details.time;
    if (details.place) payload['place'] = details.place;
    if (details.notes) payload['notes'] = details.notes;
    return this.http.post<GroupEvent>(`api/v1/groups/${groupId}/events`, payload).pipe(
      map(event => {
        this.selectedGroup.update(g => {
          if (!g) return g;
          return { ...g, events: [...g.events, event] };
        });
        this.groups.update(gs =>
          gs.map(g => g.group_id === groupId
            ? { ...g, events: [...g.events, event] }
            : g)
        );
        return event;
      }),
      catchError(() => of(null))
    );
  }

  voteOnEvent(groupId: string, eventId: string, vote: VoteOption): Observable<EventVote | null> {
    const user = this.authService.currentUser();
    if (!user) return of(null);
    const payload = {
      voter_email: user.email,
      voter_name: `${user.firstName} ${user.lastName}`,
      vote
    };
    return this.http.post<EventVote>(`api/v1/groups/${groupId}/events/${eventId}/vote`, payload).pipe(
      map(newVote => {
        const applyVote = (e: GroupEvent): GroupEvent =>
          e.event_id !== eventId ? e : {
            ...e,
            votes: [
              ...(e.votes ?? []).filter(v => v.voter_email !== newVote.voter_email),
              newVote
            ]
          };
        this.selectedGroup.update(g => {
          if (!g) return g;
          return { ...g, events: g.events.map(applyVote) };
        });
        this.groups.update(gs =>
          gs.map(g => g.group_id === groupId
            ? { ...g, events: g.events.map(applyVote) }
            : g)
        );
        return newVote;
      }),
      catchError(() => of(null))
    );
  }

  // ─── Messages ───

  postGroupMessage(groupId: string, content: string): Observable<GroupMessage | null> {
    const user = this.authService.currentUser();
    if (!user) return of(null);
    const payload = {
      author_email: user.email,
      author_name: `${user.firstName} ${user.lastName}`,
      content
    };
    return this.http.post<GroupMessage>(`api/v1/groups/${groupId}/messages`, payload).pipe(
      map(msg => {
        this.selectedGroup.update(g => {
          if (!g) return g;
          return { ...g, messages: [...g.messages, msg] };
        });
        return msg;
      }),
      catchError(() => of(null))
    );
  }

  postEventMessage(groupId: string, eventId: string, content: string): Observable<GroupMessage | null> {
    const user = this.authService.currentUser();
    if (!user) return of(null);
    const payload = {
      author_email: user.email,
      author_name: `${user.firstName} ${user.lastName}`,
      content
    };
    return this.http.post<GroupMessage>(`api/v1/groups/${groupId}/events/${eventId}/messages`, payload).pipe(
      map(msg => {
        this.selectedGroup.update(g => {
          if (!g) return g;
          return {
            ...g,
            events: g.events.map(e =>
              e.event_id === eventId
                ? { ...e, messages: [...e.messages, msg] }
                : e
            )
          };
        });
        return msg;
      }),
      catchError(() => of(null))
    );
  }

  // ─── Players ───

  loadAllPlayers() {
    this.http.get<any[]>('api/v1/players').pipe(
      map(list => list.map((p: any) => ({
        id: p._id || p.id || '',
        firstName: p.firstName || '',
        lastName: p.lastName || '',
        email: p.email || '',
        dupr_rating: p.dupr_rating || 0
      }))),
      catchError(() => of([]))
    ).subscribe(players => this.allPlayers.set(players));
  }

  refreshSelectedGroup() {
    const g = this.selectedGroup();
    if (g) this.selectGroup(g.group_id);
  }
}
