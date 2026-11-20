import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/json.dart';
import '../../core/state.dart';
import '../../core/theme.dart';
import '../../core/ui.dart';
import '../../l10n/app_localizations.dart';
import '../home/widgets.dart';
import 'live.dart';
import 'mascot.dart';

/// Mascot tab: live talk, Noticed (patterns) and Pulse (markets and the world).
class MascotScreen extends ConsumerStatefulWidget {
  const MascotScreen({super.key, required this.active});
  final bool active;

  @override
  ConsumerState<MascotScreen> createState() => _MascotScreenState();
}

class _MascotScreenState extends ConsumerState<MascotScreen> {
  int _segment = 0;

  @override
  void didUpdateWidget(MascotScreen old) {
    super.didUpdateWidget(old);
    if (widget.active && !old.active) {
      Future.microtask(() => ref.read(liveProvider('chat').notifier).connect());
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final app = ref.watch(appProvider);
    final labels = [l.mascotTalk, l.mascotNoticed, l.mascotPulse];
    return SafeArea(
      bottom: false,
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(Pk.pad, 14, Pk.pad, 8),
            child: Row(
              children: [
                for (final (i, label) in labels.indexed) ...[
                  PChip(label: i == 1 && app.insights.isNotEmpty ? '$label · ${app.insights.length}' : label, selected: _segment == i, onTap: () => setState(() => _segment = i)),
                  const SizedBox(width: 8),
                ],
              ],
            ),
          ),
          Expanded(
            child: switch (_segment) {
              0 => const TalkPanel(mode: 'chat'),
              1 => _Noticed(insights: app.insights),
              _ => _Pulse(items: app.pulse.l('items')),
            },
          ),
        ],
      ),
    );
  }
}

class _Noticed extends ConsumerWidget {
  const _Noticed({required this.insights});
  final List<Json> insights;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = L.of(context);
    if (insights.isEmpty) return Center(child: StateNote(icon: Icons.visibility_outlined, title: l.noInsights, body: l.noInsightsBody));
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(Pk.pad, 8, Pk.pad, 120),
      itemCount: insights.length,
      separatorBuilder: (_, _) => const SizedBox(height: Pk.gap),
      itemBuilder: (context, i) {
        final it = insights[i];
        final sev = it.i('severity');
        final color = sev >= 3 ? Pk.coral : sev == 2 ? Pk.amber : Pk.muted;
        return Rise(
          index: i,
          child: PCard(
            border: color.withValues(alpha: 0.45),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(width: 8, height: 8, color: color),
                    const SizedBox(width: 8),
                    Expanded(child: Text((i + 1).toString().padLeft(2, '0'), style: Pk.label(c: color))),
                    Pressable(
                      onTap: () => ref.read(appProvider.notifier).dismissInsight(it.s('id')),
                      semantics: l.dismiss,
                      child: const Padding(padding: EdgeInsets.all(6), child: Icon(Icons.close, size: 16, color: Pk.faint)),
                    ),
                  ],
                ),
                InsightBody(insight: it),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _Pulse extends StatelessWidget {
  const _Pulse({required this.items});
  final List<Json> items;

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    if (items.isEmpty) return Center(child: StateNote(icon: Icons.public_outlined, title: l.pulseEmpty, body: l.pulseEmptyBody));
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(Pk.pad, 8, Pk.pad, 120),
      itemCount: items.length,
      separatorBuilder: (_, _) => const SizedBox(height: Pk.gap),
      itemBuilder: (context, i) => Rise(
        index: i,
        child: PCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [SectionLabel(items[i].s('topic'), index: i + 1), const SizedBox(height: 12), PulseBody(item: items[i])],
          ),
        ),
      ),
    );
  }
}

/// The conversation: mascot stage, transcript, confirm card, text box and mic. Used by the
/// Mascot tab (`chat`) and by onboarding (`onboarding`).
class TalkPanel extends ConsumerStatefulWidget {
  const TalkPanel({super.key, required this.mode, this.compact = false, this.bottomInset = 96});
  final String mode;
  final bool compact;
  final double bottomInset;

  @override
  ConsumerState<TalkPanel> createState() => _TalkPanelState();
}

class _TalkPanelState extends ConsumerState<TalkPanel> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final _focus = FocusNode();

  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(liveProvider(widget.mode).notifier).connect());
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    _focus.dispose();
    super.dispose();
  }

  void _send([String? preset]) {
    final text = (preset ?? _input.text).trim();
    if (text.isEmpty) return;
    final live = ref.read(liveProvider(widget.mode).notifier);
    live.enableSpeaker(); // a tap is a user gesture: browsers allow audio from here on
    live.sendText(text);
    _input.clear();
  }

  void _scrollDown() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) _scroll.animateTo(_scroll.position.maxScrollExtent, duration: Pk.med, curve: Pk.ease);
    });
  }

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final provider = liveProvider(widget.mode);
    final live = ref.watch(provider);
    final notifier = ref.read(provider.notifier);
    final offline = ref.watch(appProvider.select((s) => s.offline));

    ref.listen(provider.select((s) => s.lines.length + (s.proposal == null ? 0 : 1)), (_, _) => _scrollDown());
    ref.listen(provider.select((s) => s.sheetSeq), (prev, next) {
      final w = ref.read(provider).sheetWidget;
      if (w == null || next == prev) return;
      final built = buildCatalogWidget(w.s('type'), params: w.m('params'), variant: 'default', index: 0);
      if (built != null) showPocketSheet<void>(context, title: widgetTitle(l, w.s('type')), builder: (_) => built);
    });

    final closed = live.status == 'closed' || live.status == 'error' || offline;
    final status = closed
        ? l.mascotOffline
        : live.status == 'connecting'
            ? l.connecting
            : live.error ?? (live.voice ? (live.micOn ? l.micStop : l.micStart) : l.voiceOffNote);
    final prompts = [l.promptToday, l.promptSpend, l.promptNotice, l.promptFund, l.promptBills];

    return Column(
      children: [
        _Stage(controller: notifier.mascot, size: widget.compact ? 124 : 156, status: status, closed: closed, onRetry: closed ? notifier.connect : null),
        Expanded(
          child: ListView(
            controller: _scroll,
            padding: const EdgeInsets.fromLTRB(Pk.pad, 4, Pk.pad, 12),
            children: [
              for (final line in live.lines) _Bubble(line: line),
              if (live.proposal != null)
                Padding(
                  padding: const EdgeInsets.only(top: 6, bottom: 6),
                  child: Rise(
                    child: ProposalCard(
                      proposal: live.proposal!,
                      onDone: (accepted) {
                        notifier.clearProposal();
                        if (accepted) notifier.celebrate();
                      },
                    ),
                  ),
                ),
              if (live.lines.isEmpty && widget.mode == 'chat' && !closed)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Wrap(spacing: 8, runSpacing: 2, children: [for (final p in prompts) PChip(label: p, onTap: live.ready ? () => _send(p) : null)]),
                ),
            ],
          ),
        ),
        Container(
          decoration: const BoxDecoration(color: Pk.ink, border: Border(top: BorderSide(color: Pk.line))),
          padding: EdgeInsets.fromLTRB(Pk.pad, 10, Pk.pad, 10 + widget.bottomInset),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _input,
                  focusNode: _focus,
                  enabled: live.ready,
                  onSubmitted: (_) {
                    _send();
                    _focus.requestFocus();
                  },
                  textInputAction: TextInputAction.send,
                  style: Pk.text(15.5),
                  cursorColor: Pk.lime,
                  decoration: InputDecoration(hintText: l.typeHint, isDense: true),
                ),
              ),
              const SizedBox(width: 8),
              _SquareButton(icon: Icons.arrow_upward, label: l.done, onTap: live.ready ? _send : null),
              if (live.voice) ...[
                const SizedBox(width: 8),
                _SquareButton(
                  icon: live.micOn ? Icons.stop : Icons.mic_none,
                  label: live.micOn ? l.micStop : l.micStart,
                  filled: true,
                  color: live.micOn ? Pk.coral : Pk.lime,
                  onTap: live.ready ? () => notifier.toggleMic() : null,
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _Stage extends StatelessWidget {
  const _Stage({required this.controller, required this.size, required this.status, required this.closed, this.onRetry});
  final MascotController controller;
  final double size;
  final String status;
  final bool closed;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.fromLTRB(Pk.pad, 0, Pk.pad, 8),
      decoration: BoxDecoration(color: Pk.surface, borderRadius: BorderRadius.circular(Pk.r), border: Border.all(color: Pk.line)),
      clipBehavior: Clip.antiAlias,
      child: Stack(
        children: [
          Positioned.fill(child: CustomPaint(painter: _GridPainter())),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
            child: Row(
              children: [
                Mascot(controller: controller, size: size),
                const SizedBox(width: 6),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text('POKO', style: Pk.label(c: Pk.lime)),
                      const SizedBox(height: 6),
                      ListenableBuilder(
                        listenable: controller,
                        builder: (context, _) => AnimatedSwitcher(
                          duration: Pk.med,
                          child: Text(
                            controller.mood.name.toUpperCase(),
                            key: ValueKey(controller.mood),
                            style: Pk.num(20, c: closed ? Pk.faint : Pk.bone, ls: 0.5),
                          ),
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(status, style: Pk.text(13, c: closed ? Pk.amber : Pk.muted, h: 1.35)),
                      if (onRetry != null) ...[const SizedBox(height: 8), GhostButton(label: L.of(context).retry, dense: true, onTap: onRetry)],
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Faint graph-paper grid behind the mascot.
class _GridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()..color = Pk.line.withValues(alpha: 0.55)..strokeWidth = 1;
    for (double x = 0; x < size.width; x += 22) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), p);
    }
    for (double y = 0; y < size.height; y += 22) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), p);
    }
  }

  @override
  bool shouldRepaint(_GridPainter old) => false;
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.line});
  final ChatLine line;

  @override
  Widget build(BuildContext context) {
    final mine = line.role == 'user';
    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 340),
        margin: const EdgeInsets.symmetric(vertical: 5),
        padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 10),
        decoration: BoxDecoration(
          color: mine ? Pk.bone : Pk.surface,
          borderRadius: BorderRadius.circular(Pk.r),
          border: Border.all(color: mine ? Pk.bone : Pk.line),
        ),
        child: Text(line.text, style: Pk.text(15.5, c: mine ? Pk.ink : Pk.bone.withValues(alpha: line.pending ? 0.7 : 1), h: 1.42)),
      ),
    );
  }
}

class _SquareButton extends StatelessWidget {
  const _SquareButton({required this.icon, required this.label, this.onTap, this.filled = false, this.color = Pk.lime});
  final IconData icon;
  final String label;
  final VoidCallback? onTap;
  final bool filled;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onTap: onTap,
      semantics: label,
      scale: 0.92,
      child: AnimatedContainer(
        duration: Pk.fast,
        width: 48,
        height: 48,
        decoration: BoxDecoration(
          color: filled ? color : Pk.surface,
          borderRadius: BorderRadius.circular(Pk.rSm),
          border: Border.all(color: filled ? color : Pk.lineStrong),
        ),
        child: Icon(icon, size: 21, color: filled ? Pk.ink : Pk.bone),
      ),
    );
  }
}
