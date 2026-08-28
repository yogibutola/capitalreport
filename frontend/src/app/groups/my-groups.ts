import { Component, inject, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { GroupsService, Group, GroupEvent, VoteOption, VOTE_OPTIONS } from './groups.service';
import { AuthService } from '../auth/auth';
import { ToastService } from '../shared/toast.service';

@Component({
  selector: 'app-my-groups',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './my-groups.html',
  styleUrl: './my-groups.css'
})
export class MyGroupsComponent implements OnInit {
  groupsService = inject(GroupsService);
  authService = inject(AuthService);
  private toast = inject(ToastService);

  // Modal state
  showCreateGroupModal = signal(false);
  showAddPlayerModal = signal(false);
  showAddEventModal = signal(false);

  // Create group form
  newGroupName = '';
  newGroupDescription = '';

  // Add event form
  newEventTitle = '';
  newEventDate = '';
  newEventTime = '';
  newEventPlace = '';
  newEventNotes = '';

  // Voting
  voteOptions = VOTE_OPTIONS;

  // Add player search
  playerSearchQuery = '';
  addPlayerError = '';

  // Discussion tabs
  activeTab = signal<'group' | 'event'>('group');
  selectedEventId = signal<string | null>(null);

  // Message input
  groupMessageText = '';
  eventMessageText = '';

  // One-click event creation
  isCreatingEvent = signal(false);

  // Filtered players for search
  filteredPlayers = computed(() => {
    const q = this.playerSearchQuery.toLowerCase().trim();
    if (!q) return this.groupsService.allPlayers();
    return this.groupsService.allPlayers().filter(p =>
      p.email.toLowerCase().includes(q) ||
      `${p.firstName} ${p.lastName}`.toLowerCase().includes(q)
    );
  });

  selectedEvent = computed(() => {
    const g = this.groupsService.selectedGroup();
    const id = this.selectedEventId();
    if (!g || !id) return null;
    return g.events.find(e => e.event_id === id) ?? null;
  });

  currentUserEmail = computed(() => this.authService.currentUser()?.email ?? '');

  ngOnInit() {
    this.groupsService.loadGroupsForCurrentUser();
    this.groupsService.loadAllPlayers();
  }

  selectGroup(group: Group) {
    this.groupsService.selectGroup(group.group_id);
    this.activeTab.set('group');
    this.selectedEventId.set(null);
  }

  openCreateGroupModal() {
    this.newGroupName = '';
    this.newGroupDescription = '';
    this.showCreateGroupModal.set(true);
  }

  createGroup() {
    if (!this.newGroupName.trim()) return;
    this.groupsService.createGroup(this.newGroupName.trim(), this.newGroupDescription.trim())
      .subscribe({
        next: group => {
          if (group) {
            this.showCreateGroupModal.set(false);
            this.groupsService.selectGroup(group.group_id);
            this.toast.success('Group created.');
          } else {
            this.toast.error("We couldn't create the group. Please try again.");
          }
        },
        error: () => this.toast.error("We couldn't create the group. Please try again."),
      });
  }

  openAddPlayerModal() {
    this.playerSearchQuery = '';
    this.addPlayerError = '';
    this.showAddPlayerModal.set(true);
  }

  addPlayer(email: string) {
    const g = this.groupsService.selectedGroup();
    if (!g) return;
    this.addPlayerError = '';
    this.groupsService.addMember(g.group_id, email).subscribe({
      next: ok => {
        if (ok) {
          this.showAddPlayerModal.set(false);
          this.toast.success('Player added to the group.');
        } else {
          this.addPlayerError = "We couldn't add that player. Please try again.";
        }
      },
      error: () => {
        this.addPlayerError = "We couldn't add that player. Please try again.";
      },
    });
  }

  openAddEventModal() {
    this.newEventTitle = '';
    this.newEventDate = new Date().toISOString().slice(0, 10);
    this.newEventTime = '';
    this.newEventPlace = '';
    this.newEventNotes = '';
    this.showAddEventModal.set(true);
  }

  createEvent() {
    const g = this.groupsService.selectedGroup();
    if (!g || this.isCreatingEvent() || !this.newEventDate) return;
    this.isCreatingEvent.set(true);
    this.groupsService.addEvent(g.group_id, {
      title: this.newEventTitle.trim() || undefined,
      date: this.newEventDate,
      time: this.newEventTime || undefined,
      place: this.newEventPlace.trim() || undefined,
      notes: this.newEventNotes.trim() || undefined
    }).subscribe({
      next: event => {
        this.isCreatingEvent.set(false);
        if (event) {
          this.showAddEventModal.set(false);
          this.activeTab.set('event');
          this.selectedEventId.set(event.event_id);
          this.toast.success('Event added.');
        } else {
          this.toast.error("We couldn't add the event. Please try again.");
        }
      },
      error: () => {
        this.isCreatingEvent.set(false);
        this.toast.error("We couldn't add the event. Please try again.");
      },
    });
  }

  castVote(option: VoteOption) {
    const g = this.groupsService.selectedGroup();
    const eventId = this.selectedEventId();
    if (!g || !eventId) return;
    this.groupsService.voteOnEvent(g.group_id, eventId, option).subscribe();
  }

  myVote = computed<VoteOption | null>(() => {
    const event = this.selectedEvent();
    if (!event) return null;
    const me = this.currentUserEmail().toLowerCase();
    return event.votes?.find(v => v.voter_email.toLowerCase() === me)?.vote ?? null;
  });

  voteCount(event: GroupEvent, option: VoteOption): number {
    return (event.votes ?? []).filter(v => v.vote === option).length;
  }

  votersFor(event: GroupEvent, option: VoteOption): string {
    return (event.votes ?? [])
      .filter(v => v.vote === option)
      .map(v => v.voter_name)
      .join(', ');
  }

  selectEvent(eventId: string) {
    this.selectedEventId.set(eventId);
    this.activeTab.set('event');
    this.eventMessageText = '';
  }

  sendGroupMessage() {
    const g = this.groupsService.selectedGroup();
    if (!g || !this.groupMessageText.trim()) return;
    const text = this.groupMessageText.trim();
    this.groupMessageText = '';
    this.groupsService.postGroupMessage(g.group_id, text).subscribe();
  }

  sendEventMessage() {
    const g = this.groupsService.selectedGroup();
    const eventId = this.selectedEventId();
    if (!g || !eventId || !this.eventMessageText.trim()) return;
    const text = this.eventMessageText.trim();
    this.eventMessageText = '';
    this.groupsService.postEventMessage(g.group_id, eventId, text).subscribe();
  }

  getInitials(name: string): string {
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  }

  getEmailInitials(email: string): string {
    return email.slice(0, 2).toUpperCase();
  }

  formatDate(dateStr: string): string {
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        weekday: 'short', month: 'short', day: 'numeric', year: 'numeric'
      });
    } catch {
      return dateStr;
    }
  }

  formatTime(ts: string): string {
    try {
      return new Date(ts).toLocaleTimeString('en-US', {
        hour: '2-digit', minute: '2-digit', hour12: true
      });
    } catch {
      return '';
    }
  }

  isMyMessage(authorEmail: string): boolean {
    return authorEmail.toLowerCase() === this.currentUserEmail().toLowerCase();
  }

  closeModals() {
    this.showCreateGroupModal.set(false);
    this.showAddPlayerModal.set(false);
    this.showAddEventModal.set(false);
  }

  formatEventTime(time: string): string {
    const [h, m] = time.split(':').map(Number);
    if (isNaN(h) || isNaN(m)) return time;
    const suffix = h >= 12 ? 'PM' : 'AM';
    const hour12 = h % 12 === 0 ? 12 : h % 12;
    return `${hour12}:${String(m).padStart(2, '0')} ${suffix}`;
  }

  trackByGroupId(_: number, g: Group) { return g.group_id; }
  trackByEventId(_: number, e: GroupEvent) { return e.event_id; }
}
