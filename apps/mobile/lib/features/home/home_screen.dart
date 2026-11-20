import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/json.dart';
import '../../core/state.dart';
import '../../core/theme.dart';
import '../../core/ui.dart';
import '../../l10n/app_localizations.dart';
import 'renderer/a2ui_home_renderer.dart';
import 'renderer/direct_renderer.dart';
import 'widgets.dart';

String asOfText(BuildContext context, DateTime? t) {
  if (t == null) return '—';
  final locale = Localizations.localeOf(context).languageCode;
  return DateFormat('d MMM, h:mm a', locale).format(t);
}

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final app = ref.watch(appProvider);
    final l = L.of(context);
    if (app.bundle == null || !app.linked) {
      return SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(Pk.pad),
          child: app.loading
              ? ListView(children: const [SizedBox(height: 60), Skeleton(height: 210), SizedBox(height: 12), Skeleton(height: 150), SizedBox(height: 12), Skeleton(height: 120)])
              : Center(
                  child: StateNote(
                    icon: app.offline ? Icons.cloud_off_outlined : Icons.error_outline,
                    title: l.errorTitle,
                    body: l.errorBody,
                    action: l.retry,
                    onAction: () => ref.read(appProvider.notifier).sync(),
                  ),
                ),
        ),
      );
    }
    final entries = renderHome(app.home);
    final hour = DateTime.now().hour;
    final greeting = hour < 12 ? l.greetMorning : hour < 17 ? l.greetAfternoon : l.greetEvening;
    final nudge = app.nudges.firstOrNull;
    return SafeArea(
      bottom: false,
      child: RefreshIndicator(
        color: Pk.limeInk,
        backgroundColor: Pk.lime,
        onRefresh: () => ref.read(appProvider.notifier).sync(),
        child: ListView(
          padding: const EdgeInsets.fromLTRB(Pk.pad, 14, Pk.pad, 120),
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(greeting.toUpperCase(), style: Pk.label(c: Pk.faint)),
                      const SizedBox(height: 4),
                      Text(app.me.s('first_name'), maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.text(30, w: FontWeight.w600, h: 1.1, ls: -0.6)),
                    ],
                  ),
                ),
                Pressable(
                  onTap: () => context.push('/profile'),
                  semantics: l.profileTitle,
                  child: InitialTile(app.me.s('display_name', '?'), size: 42),
                ),
              ],
            ),
            const SizedBox(height: 16),
            if (app.offline) ...[_OfflineBanner(text: l.offlineBanner(asOfText(context, app.asOf))), const SizedBox(height: Pk.gap)],
            if (nudge != null) ...[_NudgeCard(nudge: nudge), const SizedBox(height: Pk.gap)],
            // Drawn by a2ui_flutter from the stored A2UI messages; the direct renderer is the fallback.
            HomeSurface(home: app.home),
            const SizedBox(height: 6),
            Row(
              children: [
                Expanded(child: GhostButton(label: l.whyLayout, icon: Icons.help_outline, dense: true, onTap: () => _showWhy(context, entries, app.home))),
                const SizedBox(width: 10),
                Expanded(child: GhostButton(label: l.editHome, icon: Icons.tune, dense: true, onTap: () => _showEdit(context, ref, entries))),
              ],
            ),
            const SizedBox(height: 14),
            Center(child: Text(l.asOf(asOfText(context, app.asOf)).toUpperCase(), style: Pk.label(c: Pk.faint, size: 10))),
          ],
        ),
      ),
    );
  }

  void _showWhy(BuildContext context, List<HomeEntry> entries, Json home) {
    final l = L.of(context);
    final summary = home.m('spec').s('summary');
    showPocketSheet<void>(
      context,
      title: l.whyLayoutTitle,
      builder: (ctx) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (summary.isNotEmpty) ...[Text(summary, style: Pk.text(16, h: 1.45)), const Stitch(vertical: 16)],
          for (final (i, e) in entries.indexed)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(width: 30, child: Text((i + 1).toString().padLeft(2, '0'), style: Pk.num(13, c: Pk.lime))),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(widgetTitle(l, e.type), style: Pk.text(15.5, w: FontWeight.w600)),
                        if ((e.reason ?? '').isNotEmpty) Padding(padding: const EdgeInsets.only(top: 3), child: Text(e.reason!, style: Pk.text(14, c: Pk.muted, h: 1.4))),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          const SizedBox(height: 10),
          // How this layout reached the screen: as A2UI messages drawn by a2ui_flutter, or the plain fallback.
          Text(
            (checkA2uiSurface(home).ok ? l.layoutMetaA2ui(home.l('a2ui').first.s('version'), home.i('version')) : l.layoutMetaPlain(home.i('version'))).toUpperCase(),
            style: Pk.label(c: Pk.faint, size: 10),
          ),
          const SizedBox(height: 14),
          GhostButton(
            label: l.askPokoChange,
            icon: Icons.mic_none,
            onTap: () {
              Navigator.of(ctx).pop();
              ProviderScope.containerOf(context).read(tabProvider.notifier).go(2);
            },
          ),
        ],
      ),
    );
  }

  void _showEdit(BuildContext context, WidgetRef ref, List<HomeEntry> entries) {
    final l = L.of(context);
    showPocketSheet<void>(context, title: l.editHome, tall: true, builder: (ctx) => _EditHome(entries: entries.where((e) => e.type != 'safe_to_spend').toList()));
  }
}

class _OfflineBanner extends StatelessWidget {
  const _OfflineBanner({required this.text});
  final String text;
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(border: Border.all(color: Pk.amber.withValues(alpha: 0.6)), borderRadius: BorderRadius.circular(Pk.rSm)),
      child: Row(
        children: [
          const Icon(Icons.cloud_off_outlined, size: 16, color: Pk.amber),
          const SizedBox(width: 10),
          Expanded(child: Text(text, style: Pk.text(13.5, c: Pk.amber, h: 1.3))),
        ],
      ),
    );
  }
}

class _NudgeCard extends ConsumerWidget {
  const _NudgeCard({required this.nudge});
  final Json nudge;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = L.of(context);
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 12, 6, 12),
      decoration: BoxDecoration(color: Pk.bone, borderRadius: BorderRadius.circular(Pk.r)),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(padding: EdgeInsets.only(top: 2), child: Icon(Icons.notifications_none, size: 18, color: Pk.ink)),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(nudge.s('title'), style: Pk.text(15, w: FontWeight.w600, c: Pk.ink, h: 1.25)),
                const SizedBox(height: 2),
                Text(nudge.s('body'), style: Pk.text(13.5, c: const Color(0xFF45463D), h: 1.35)),
              ],
            ),
          ),
          IconButton(
            tooltip: l.dismiss,
            onPressed: () => ref.read(appProvider.notifier).dismissNudge(nudge.s('id')),
            icon: const Icon(Icons.close, size: 18, color: Pk.ink),
          ),
        ],
      ),
    );
  }
}

/// Long-press / Edit: reorder or hide. Saves a manual layout version. Safe-to-spend is not in
/// this list at all, so it cannot be moved or hidden.
class _EditHome extends ConsumerStatefulWidget {
  const _EditHome({required this.entries});
  final List<HomeEntry> entries;

  @override
  ConsumerState<_EditHome> createState() => _EditHomeState();
}

class _EditHomeState extends ConsumerState<_EditHome> {
  late final List<HomeEntry> _order = [...widget.entries];
  late final Set<String> _hidden = {};
  bool _busy = false;

  String _key(HomeEntry e) => '${e.type}:${e.params.s('group_id')}';

  Future<void> _save() async {
    setState(() => _busy = true);
    final l = L.of(context);
    final widgets = [for (final e in _order) if (!_hidden.contains(_key(e))) e.toSpec()];
    await ref.read(appProvider.notifier).manualLayout(widgets);
    if (!mounted) return;
    Navigator.of(context).pop();
    toast(context, l.homeSaved);
  }

  @override
  Widget build(BuildContext context) {
    final l = L.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(l.editHomeHint, style: Pk.text(14, c: Pk.muted, h: 1.4)),
        const SizedBox(height: 12),
        _row(l.safeToSpend, pinned: true),
        ReorderableListView(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          buildDefaultDragHandles: false,
          proxyDecorator: (child, _, _) => Material(color: Colors.transparent, child: child),
          onReorderItem: (from, to) => setState(() => _order.insert(to, _order.removeAt(from))),
          children: [
            for (final (i, e) in _order.indexed)
              KeyedSubtree(
                key: ValueKey(_key(e)),
                child: _row(
                  widgetTitle(l, e.type),
                  hidden: _hidden.contains(_key(e)),
                  onToggle: () => setState(() => _hidden.contains(_key(e)) ? _hidden.remove(_key(e)) : _hidden.add(_key(e))),
                  handle: ReorderableDragStartListener(index: i, child: const Padding(padding: EdgeInsets.all(10), child: Icon(Icons.drag_indicator, size: 20, color: Pk.muted))),
                ),
              ),
          ],
        ),
        const SizedBox(height: 16),
        BlockButton(label: l.save, busy: _busy, onTap: _save),
        const SizedBox(height: 10),
        GhostButton(
          label: l.resetHome,
          onTap: () async {
            await ref.read(appProvider.notifier).resetLayout();
            if (context.mounted) Navigator.of(context).pop();
          },
        ),
      ],
    );
  }

  Widget _row(String title, {bool pinned = false, bool hidden = false, VoidCallback? onToggle, Widget? handle}) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.only(left: 14),
      height: 52,
      decoration: BoxDecoration(color: Pk.raised, borderRadius: BorderRadius.circular(Pk.rSm), border: Border.all(color: pinned ? Pk.lime.withValues(alpha: 0.5) : Pk.line)),
      child: Row(
        children: [
          Expanded(child: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.text(15, w: FontWeight.w500, c: hidden ? Pk.faint : Pk.bone))),
          if (pinned) const Padding(padding: EdgeInsets.only(right: 14), child: Icon(Icons.push_pin_outlined, size: 18, color: Pk.lime)),
          if (onToggle != null) IconButton(onPressed: onToggle, icon: Icon(hidden ? Icons.visibility_off_outlined : Icons.visibility_outlined, size: 19, color: hidden ? Pk.faint : Pk.bone)),
          ?handle,
        ],
      ),
    );
  }
}
