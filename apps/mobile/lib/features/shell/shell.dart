import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/state.dart';
import '../../core/theme.dart';
import '../../core/ui.dart';
import '../../l10n/app_localizations.dart';
import '../collab/collab_screen.dart';
import '../home/home_screen.dart';
import '../mascot/mascot.dart';
import '../mascot/mascot_screen.dart';
import '../money/money_screen.dart';
import '../plan/plan_screen.dart';

/// Five tabs, mascot in the centre. Only Home is generated; the rest stay put.
class Shell extends ConsumerWidget {
  const Shell({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tab = ref.watch(tabProvider);
    final l = L.of(context);
    final offline = ref.watch(appProvider.select((s) => s.offline));
    return Scaffold(
      extendBody: true,
      body: IndexedStack(
        index: tab,
        children: [
          const HomeScreen(),
          const MoneyScreen(),
          MascotScreen(active: tab == 2),
          const PlanScreen(),
          const CollabScreen(),
        ],
      ),
      bottomNavigationBar: _NavBar(
        index: tab,
        onTap: ref.read(tabProvider.notifier).go,
        labels: [l.tabHome, l.tabMoney, l.tabMascot, l.tabPlan, l.tabCollab],
        mascotMood: offline ? MascotMood.sleepy : MascotMood.idle,
      ),
    );
  }
}

class _NavBar extends StatelessWidget {
  const _NavBar({required this.index, required this.onTap, required this.labels, required this.mascotMood});
  final int index;
  final void Function(int) onTap;
  final List<String> labels;
  final MascotMood mascotMood;

  static const _icons = [Icons.home_outlined, Icons.receipt_long_outlined, null, Icons.donut_large_outlined, Icons.group_outlined];

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).padding.bottom;
    return Container(
      decoration: const BoxDecoration(color: Pk.ink, border: Border(top: BorderSide(color: Pk.line))),
      padding: EdgeInsets.only(bottom: bottom),
      child: SizedBox(
        height: 66,
        child: Row(
          children: [
            for (var i = 0; i < 5; i++)
              Expanded(
                child: i == 2
                    ? _MascotTab(selected: index == 2, label: labels[2], mood: mascotMood, onTap: () => onTap(2))
                    : Pressable(
                        onTap: () => onTap(i),
                        semantics: labels[i],
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            AnimatedContainer(duration: Pk.fast, width: index == i ? 18 : 0, height: 2, color: Pk.lime),
                            const SizedBox(height: 7),
                            Icon(_icons[i], size: 22, color: index == i ? Pk.bone : Pk.faint),
                            const SizedBox(height: 4),
                            Text(labels[i].toUpperCase(), maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.label(c: index == i ? Pk.bone : Pk.faint, size: 9.5)),
                          ],
                        ),
                      ),
              ),
          ],
        ),
      ),
    );
  }
}

/// The centre button is the mascot itself, sitting a little proud of the bar.
class _MascotTab extends StatelessWidget {
  const _MascotTab({required this.selected, required this.label, required this.mood, required this.onTap});
  final bool selected;
  final String label;
  final MascotMood mood;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onTap: onTap,
      semantics: label,
      scale: 0.94,
      child: OverflowBox(
        maxHeight: 96,
        alignment: Alignment.bottomCenter,
        child: Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: AnimatedContainer(
            duration: Pk.med,
            curve: Pk.ease,
            width: 62,
            height: 62,
            decoration: BoxDecoration(
              color: selected ? Pk.raised : Pk.surface,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: selected ? Pk.lime : Pk.lineStrong, width: selected ? 1.5 : 1),
            ),
            child: Center(child: PokoMark(size: 52, mood: mood == MascotMood.sleepy ? MascotMood.sleepy : (selected ? MascotMood.happy : MascotMood.idle))),
          ),
        ),
      ),
    );
  }
}

/// Screen title used by the fixed tabs.
class ScreenTitle extends StatelessWidget {
  const ScreenTitle(this.title, {super.key, this.trailing});
  final String title;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(Pk.pad, 14, Pk.pad, 12),
      child: Row(
        children: [
          Expanded(child: Text(title, style: Pk.text(30, w: FontWeight.w600, h: 1.1, ls: -0.6))),
          ?trailing,
        ],
      ),
    );
  }
}
