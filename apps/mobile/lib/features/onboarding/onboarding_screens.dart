import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/json.dart';
import '../../core/state.dart';
import '../../core/theme.dart';
import '../../core/ui.dart';
import '../../l10n/app_localizations.dart';
import '../home/renderer/a2ui_home_renderer.dart';
import '../home/widgets.dart';
import '../mascot/live.dart';
import '../mascot/mascot.dart';
import '../mascot/mascot_screen.dart';
import '../profile/profile_screen.dart';

/// First run, about two minutes: language and sign-in, a short talk, pick a persona, Home builds.
class WelcomeScreen extends ConsumerStatefulWidget {
  const WelcomeScreen({super.key});

  @override
  ConsumerState<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends ConsumerState<WelcomeScreen> {
  final _mascot = MascotController()..mood = MascotMood.happy;
  bool _busy = false;

  @override
  void dispose() {
    _mascot.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final lang = ref.watch(appProvider.select((s) => s.language));
    return Scaffold(
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, box) => SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(24, 20, 24, 24),
            child: ConstrainedBox(
              constraints: BoxConstraints(minHeight: box.maxHeight - 44),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Rise(child: Text('POCKET', style: Pk.label(c: Pk.lime, size: 13))),
                  const SizedBox(height: 28),
                  Rise(index: 1, child: Center(child: Mascot(controller: _mascot, size: 210))),
                  const SizedBox(height: 24),
                  Rise(index: 2, child: Text(l.onbTagline, style: Pk.text(38, w: FontWeight.w600, h: 1.08, ls: -1.2))),
                  const SizedBox(height: 28),
                  Rise(
                    index: 3,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(l.onbPickLanguage.toUpperCase(), style: Pk.label()),
                        const SizedBox(height: 10),
                        Wrap(
                          spacing: 8,
                          children: [for (final e in languageNames.entries) PChip(label: e.value, selected: lang == e.key, onTap: () => ref.read(appProvider.notifier).setLanguage(e.key))],
                        ),
                        const SizedBox(height: 6),
                        Text(l.onbLangHint, style: Pk.text(12.5, c: Pk.faint)),
                      ],
                    ),
                  ),
                  const SizedBox(height: 28),
                  Rise(
                    index: 4,
                    child: BlockButton(
                      label: l.onbTryDemo,
                      icon: Icons.arrow_forward,
                      busy: _busy,
                      onTap: () async {
                        setState(() => _busy = true);
                        await ref.read(appProvider.notifier).signIn();
                        if (context.mounted) context.go('/talk');
                      },
                    ),
                  ),
                  const SizedBox(height: 12),
                  Rise(index: 5, child: Text(l.onbDemoNote, style: Pk.text(12.5, c: Pk.faint, h: 1.4))),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Voice choice and the short onboarding talk (four questions). Skippable.
class TalkScreen extends ConsumerWidget {
  const TalkScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = L.of(context);
    final voice = ref.watch(appProvider.select((s) => s.me.s('mascot_voice', 'warm')));
    final live = ref.watch(liveProvider('onboarding'));
    return Scaffold(
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(Pk.pad, 16, Pk.pad, 4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(l.onbStep(2, 3).toUpperCase(), style: Pk.label(c: Pk.lime)),
                  const SizedBox(height: 8),
                  Text(l.onbTalkTitle, style: Pk.text(26, w: FontWeight.w600, h: 1.15, ls: -0.5)),
                  const SizedBox(height: 4),
                  Text(l.onbTalkHint, style: Pk.text(14, c: Pk.muted)),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Text('${l.mascotVoice.toUpperCase()}  ', style: Pk.label(c: Pk.faint, size: 10)),
                      Expanded(
                        child: SingleChildScrollView(
                          scrollDirection: Axis.horizontal,
                          child: Row(children: [for (final v in voices) Padding(padding: const EdgeInsets.only(right: 6), child: PChip(label: voiceLabel(l, v), selected: voice == v, onTap: () => ref.read(appProvider.notifier).setVoice(v)))]),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                ],
              ),
            ),
            const Expanded(child: TalkPanel(mode: 'onboarding', compact: true, bottomInset: 0)),
            Padding(
              padding: const EdgeInsets.fromLTRB(Pk.pad, 10, Pk.pad, 14),
              child: live.onboardingDone
                  ? BlockButton(label: l.continueLabel, icon: Icons.arrow_forward, onTap: () => context.go('/personas'))
                  : GhostButton(label: l.onbSkipTalk, onTap: () => context.go('/personas')),
            ),
          ],
        ),
      ),
    );
  }
}

const _personaLabels = {'student': 0, 'first_job': 1, 'family': 2, 'gig': 3, 'shop': 4, 'investor': 5};
const _personaEmoji = {'student': '🎒', 'first_job': '💼', 'family': '🏡', 'gig': '🛵', 'shop': '🏪', 'investor': '📈'};

/// Link accounts (MVP: pick a synthetic profile). The closest match from the talk is preselected.
class PersonaScreen extends ConsumerStatefulWidget {
  const PersonaScreen({super.key});

  @override
  ConsumerState<PersonaScreen> createState() => _PersonaScreenState();
}

class _PersonaScreenState extends ConsumerState<PersonaScreen> {
  String? _picked;
  bool _busy = false;

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final personas = ref.watch(fetchProvider('/v1/onboarding/personas'));
    final suggested = ref.watch(liveProvider('onboarding').select((s) => s.suggestedPersona));
    final current = ref.watch(appProvider.select((s) => s.me.sn('persona_id')));
    final picked = _picked ?? suggested ?? current ?? 'first_job';
    return Scaffold(
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(Pk.pad, 16, Pk.pad, 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(l.onbStep(3, 3).toUpperCase(), style: Pk.label(c: Pk.lime)),
                  const SizedBox(height: 8),
                  Text(l.onbPickPersona, style: Pk.text(26, w: FontWeight.w600, h: 1.15, ls: -0.5)),
                  const SizedBox(height: 4),
                  Text(l.onbPersonaNote, style: Pk.text(14, c: Pk.muted, h: 1.35)),
                ],
              ),
            ),
            Expanded(
              child: personas.when(
                loading: () => ListView(padding: const EdgeInsets.all(Pk.pad), children: const [Skeleton(height: 88), SizedBox(height: 10), Skeleton(height: 88), SizedBox(height: 10), Skeleton(height: 88)]),
                error: (_, _) => Center(child: StateNote(icon: Icons.cloud_off_outlined, title: l.errorTitle, body: l.errorBody, action: l.retry, onAction: () => ref.invalidate(fetchProvider('/v1/onboarding/personas')))),
                data: (d) => ListView(
                  padding: const EdgeInsets.fromLTRB(Pk.pad, 6, Pk.pad, 12),
                  children: [
                    for (final (i, p) in d.l('personas').indexed)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: Rise(index: i, step: 50, child: _PersonaCard(p: p, selected: picked == p.s('persona_id'), suggested: suggested == p.s('persona_id'), onTap: () => setState(() => _picked = p.s('persona_id')))),
                      ),
                  ],
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(Pk.pad, 8, Pk.pad, 14),
              child: BlockButton(
                label: l.onbBuild,
                icon: Icons.auto_awesome_outlined,
                busy: _busy,
                onTap: () async {
                  setState(() => _busy = true);
                  final ok = await ref.read(appProvider.notifier).link(picked);
                  if (!context.mounted) return;
                  setState(() => _busy = false);
                  if (ok) {
                    await ref.read(liveProvider('onboarding').notifier).disconnect();
                    await ref.read(liveProvider('chat').notifier).disconnect();
                    if (context.mounted) context.go('/building');
                  } else {
                    toast(context, l.errorTitle);
                  }
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PersonaCard extends StatelessWidget {
  const _PersonaCard({required this.p, required this.selected, required this.suggested, required this.onTap});
  final Json p;
  final bool selected;
  final bool suggested;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final id = p.s('persona_id');
    return Pressable(
      onTap: onTap,
      scale: 0.985,
      child: AnimatedContainer(
        duration: Pk.fast,
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: selected ? Pk.raised : Pk.surface,
          borderRadius: BorderRadius.circular(Pk.r),
          border: Border.all(color: selected ? Pk.lime : Pk.line, width: selected ? 1.5 : 1),
        ),
        child: Row(
          children: [
            EmojiTile(_personaEmoji[id] ?? '•', size: 46),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(child: Text('${p.s('first_name')}, ${p.i('age')}', maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.text(17, w: FontWeight.w600))),
                      const SizedBox(width: 8),
                      if (suggested) Tag(l.onbSuggested, color: Pk.lime),
                    ],
                  ),
                  const SizedBox(height: 3),
                  Text('${p.s('occupation')} · ${p.s('city')}', maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.text(13.5, c: Pk.muted)),
                  const SizedBox(height: 2),
                  Text('${((_personaLabels[id] ?? 0) + 1).toString().padLeft(2, '0')} · ${languageNames[p.s('language')] ?? ''}', style: Pk.label(c: Pk.faint, size: 10)),
                ],
              ),
            ),
            AnimatedContainer(
              duration: Pk.fast,
              width: 20,
              height: 20,
              decoration: BoxDecoration(color: selected ? Pk.lime : Colors.transparent, border: Border.all(color: selected ? Pk.lime : Pk.lineStrong), borderRadius: BorderRadius.circular(Pk.rIn)),
              child: selected ? const Icon(Icons.check, size: 14, color: Pk.limeInk) : null,
            ),
          ],
        ),
      ),
    );
  }
}

/// Home builds itself on screen, widget by widget, while the mascot says why.
class BuildingScreen extends ConsumerStatefulWidget {
  const BuildingScreen({super.key});

  @override
  ConsumerState<BuildingScreen> createState() => _BuildingScreenState();
}

class _BuildingScreenState extends ConsumerState<BuildingScreen> {
  final _mascot = MascotController()..mood = MascotMood.thinking;
  int _shown = 0;
  bool _done = false;

  @override
  void initState() {
    super.initState();
    _run();
  }

  Future<void> _run() async {
    await Future<void>.delayed(const Duration(milliseconds: 700));
    final count = renderHome(ref.read(appProvider).home).length;
    _mascot.mood = MascotMood.talking;
    for (var i = 1; i <= count; i++) {
      if (!mounted) return;
      setState(() => _shown = i);
      await Future<void>.delayed(const Duration(milliseconds: 620));
    }
    if (!mounted) return;
    _mascot.mood = MascotMood.celebrating;
    setState(() => _done = true);
  }

  @override
  void dispose() {
    _mascot.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    final app = ref.watch(appProvider);
    final entries = renderHome(app.home);
    final summary = app.home.m('spec').s('summary');
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(Pk.pad, 16, Pk.pad, 14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Mascot(controller: _mascot, size: 112),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('${_shown.toString().padLeft(2, '0')} / ${entries.length.toString().padLeft(2, '0')}', style: Pk.num(13, c: Pk.lime)),
                        const SizedBox(height: 6),
                        Text(_done && summary.isNotEmpty ? summary : l.onbBuilding, style: Pk.text(_done ? 17 : 22, w: FontWeight.w600, h: 1.25)),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Expanded(
                child: ListView(
                  children: [
                    for (final (i, e) in entries.indexed)
                      if (i < _shown)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: Rise(
                            child: Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(color: Pk.surface, borderRadius: BorderRadius.circular(Pk.r), border: Border.all(color: i == 0 ? Pk.lime.withValues(alpha: 0.5) : Pk.line)),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  SizedBox(width: 30, child: Text((i + 1).toString().padLeft(2, '0'), style: Pk.num(13, c: i == 0 ? Pk.lime : Pk.muted))),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(widgetTitle(l, e.type), style: Pk.text(15.5, w: FontWeight.w600)),
                                        if ((e.reason ?? '').isNotEmpty) Padding(padding: const EdgeInsets.only(top: 3), child: Text(e.reason!, style: Pk.text(13.5, c: Pk.muted, h: 1.4))),
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                  ],
                ),
              ),
              AnimatedOpacity(
                opacity: _done ? 1 : 0.35,
                duration: Pk.med,
                child: BlockButton(label: l.continueLabel, icon: Icons.arrow_forward, onTap: _done ? () => context.go('/') : null),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
