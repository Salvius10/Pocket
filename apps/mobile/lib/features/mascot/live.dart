import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../../core/audio/audio_in.dart';
import '../../core/audio/audio_out.dart';
import '../../core/config.dart';
import '../../core/json.dart';
import '../../core/state.dart';
import 'mascot.dart';

class ChatLine {
  const ChatLine(this.role, this.text, {this.pending = false});
  final String role; // user | mascot
  final String text;
  final bool pending;
}

class LiveState {
  const LiveState({
    this.status = 'idle', // idle | connecting | ready | closed | error
    this.voice = false,
    this.micOn = false,
    this.lines = const [],
    this.proposal,
    this.sheetWidget,
    this.suggestedPersona,
    this.onboardingDone = false,
    this.busy = false,
    this.error,
    this.sheetSeq = 0,
  });
  final String status;
  final bool voice; // true when the agent runs the live model
  final bool micOn;
  final List<ChatLine> lines;
  final Json? proposal;
  final Json? sheetWidget;
  final int sheetSeq;
  final String? suggestedPersona;
  final bool onboardingDone;
  final bool busy; // mascot is thinking or talking
  final String? error;

  bool get ready => status == 'ready';

  LiveState copy({
    String? status, bool? voice, bool? micOn, List<ChatLine>? lines, Json? proposal, bool clearProposal = false, Json? sheetWidget,
    String? suggestedPersona, bool? onboardingDone, bool? busy, String? error, bool clearError = false, int? sheetSeq,
  }) {
    return LiveState(
      status: status ?? this.status,
      voice: voice ?? this.voice,
      micOn: micOn ?? this.micOn,
      lines: lines ?? this.lines,
      proposal: clearProposal ? null : proposal ?? this.proposal,
      sheetWidget: sheetWidget ?? this.sheetWidget,
      sheetSeq: sheetSeq ?? this.sheetSeq,
      suggestedPersona: suggestedPersona ?? this.suggestedPersona,
      onboardingDone: onboardingDone ?? this.onboardingDone,
      busy: busy ?? this.busy,
      error: clearError ? null : error ?? this.error,
    );
  }
}

/// One live conversation with the agent (ARCHITECTURE.md §7.1). `arg` is the mode: chat | onboarding.
class LiveNotifier extends Notifier<LiveState> {
  LiveNotifier(this.mode);
  final String mode;

  final MascotController mascot = MascotController();
  WebSocketChannel? _ws;
  StreamSubscription<dynamic>? _sub;
  AudioOut? _out;
  AudioIn? _in;
  Timer? _mouthTimer;
  bool _disposed = false;

  @override
  LiveState build() {
    ref.onDispose(() {
      _disposed = true;
      _teardown();
      mascot.dispose();
    });
    return const LiveState();
  }

  Future<void> connect() async {
    if (state.status == 'connecting' || state.status == 'ready') return;
    state = state.copy(status: 'connecting', clearError: true);
    final app = ref.read(appProvider);
    final auth = ref.read(authProvider);
    try {
      final ws = WebSocketChannel.connect(Uri.parse(Env.agentWs));
      await ws.ready.timeout(const Duration(seconds: 8));
      _ws = ws;
      _sub = ws.stream.listen(_onMessage, onDone: _onClosed, onError: (_) => _onClosed());
      final token = await auth.token();
      ws.sink.add(jsonEncode({
        'type': 'hello',
        'token': token,
        if (token == null) 'dev_user': auth.devUser,
        'lang': app.language,
        'voice': app.me.s('mascot_voice', 'warm'),
        'mode': mode,
      }));
    } catch (_) {
      _onClosed();
    }
  }

  void _onClosed() {
    if (_disposed) return;
    _stopMicQuietly();
    mascot.mood = MascotMood.sleepy;
    state = state.copy(status: 'closed', micOn: false, busy: false);
  }

  void _onMessage(dynamic raw) {
    if (_disposed) return;
    if (raw is List<int>) {
      // Mascot audio: PCM16 LE mono 24 kHz.
      _out?.feed(raw is Uint8List ? raw : Uint8List.fromList(raw));
      return;
    }
    if (raw is! String) return;
    final Json msg;
    try {
      msg = Map<String, dynamic>.from(jsonDecode(raw) as Map);
    } catch (_) {
      return;
    }
    switch (msg.s('type')) {
      case 'ready':
        mascot.mood = MascotMood.idle;
        state = state.copy(status: 'ready', voice: msg.b('voice'));
      case 'mood':
        final mood = moodFromName(msg.s('mood'));
        mascot.mood = mood;
        state = state.copy(busy: mood == MascotMood.thinking || mood == MascotMood.talking);
      case 'transcript':
        _onTranscript(msg.s('role'), msg.s('text'), msg.b('final'));
      case 'confirm_request':
        state = state.copy(proposal: msg.m('proposal'));
      case 'show_widget':
        state = state.copy(sheetWidget: msg.m('widget'), sheetSeq: state.sheetSeq + 1);
      case 'home_updated':
        ref.read(appProvider.notifier).applyHome(msg.m('home'));
        mascot.mood = MascotMood.happy;
      case 'onboarding_done':
        state = state.copy(onboardingDone: true, suggestedPersona: msg.sn('suggested_persona'));
      case 'profile_saved':
        state = state.copy(onboardingDone: true);
      case 'interrupted' || 'stop_audio':
        _out?.flush(); // drop queued audio at once
      case 'turn_complete':
        state = state.copy(busy: false);
      case 'error':
        mascot.mood = MascotMood.sleepy;
        state = state.copy(error: msg.s('message'), busy: false);
    }
  }

  void _onTranscript(String role, String text, bool isFinal) {
    if (text.trim().isEmpty) return;
    final lines = [...state.lines];
    if (lines.isNotEmpty && lines.last.role == role && lines.last.pending) {
      lines[lines.length - 1] = ChatLine(role, text, pending: !isFinal);
    } else if (!(lines.isNotEmpty && lines.last.role == role && lines.last.text == text)) {
      lines.add(ChatLine(role, text, pending: !isFinal));
    }
    state = state.copy(lines: lines.length > 60 ? lines.sublist(lines.length - 60) : lines);
  }

  void sendText(String text) {
    final t = text.trim();
    if (t.isEmpty || !state.ready) return;
    _out?.flush();
    mascot.mood = MascotMood.thinking;
    state = state.copy(busy: true);
    _ws?.sink.add(jsonEncode({'type': 'text', 'text': t}));
  }

  /// Call from a tap: browsers only allow audio after a user gesture.
  Future<void> _ensureAudioOut() async {
    if (_out != null) return;
    final out = createAudioOut();
    await out.init();
    _out = out;
    _mouthTimer ??= Timer.periodic(const Duration(milliseconds: 50), (_) {
      final level = _out?.level ?? 0;
      if (level > 0.01) mascot.setMouthOpen(level * 100); // lip-sync from playback loudness
    });
  }

  Future<bool> toggleMic() async {
    if (!state.ready || !state.voice) return false;
    if (state.micOn) {
      await _in?.stop();
      _ws?.sink.add(jsonEncode({'type': 'audio_end'}));
      state = state.copy(micOn: false);
      mascot.mood = MascotMood.thinking;
      return true;
    }
    await _ensureAudioOut();
    _in ??= AudioIn();
    final ok = await _in!.start((chunk) => _ws?.sink.add(chunk));
    if (ok) {
      _out?.flush();
      mascot.mood = MascotMood.listening;
      state = state.copy(micOn: true);
    }
    return ok;
  }

  Future<void> enableSpeaker() => _ensureAudioOut();

  void clearProposal() => state = state.copy(clearProposal: true);

  void celebrate() {
    mascot.mood = MascotMood.celebrating;
    Future.delayed(const Duration(milliseconds: 2400), () {
      if (!_disposed && mascot.mood == MascotMood.celebrating) mascot.mood = MascotMood.idle;
    });
  }

  void _stopMicQuietly() {
    _in?.stop();
  }

  Future<void> disconnect() async {
    await _teardown();
    if (!_disposed) state = const LiveState();
  }

  Future<void> _teardown() async {
    _mouthTimer?.cancel();
    _mouthTimer = null;
    await _sub?.cancel();
    _sub = null;
    try {
      _ws?.sink.add(jsonEncode({'type': 'bye'}));
      await _ws?.sink.close();
    } catch (_) {
      // socket already gone
    }
    _ws = null;
    await _in?.dispose();
    _in = null;
    await _out?.dispose();
    _out = null;
  }
}

final liveProvider = NotifierProvider.family<LiveNotifier, LiveState, String>(LiveNotifier.new);
