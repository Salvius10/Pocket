import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/json.dart';
import '../../core/state.dart';
import '../../core/theme.dart';
import '../../core/ui.dart';
import '../../l10n/app_localizations.dart';

const languageNames = {'en': 'English', 'hi': 'हिन्दी', 'ta': 'தமிழ்'};
const voices = ['warm', 'bright', 'calm', 'clear'];

String voiceLabel(L l, String v) => switch (v) { 'bright' => l.voiceBright, 'calm' => l.voiceCalm, 'clear' => l.voiceClear, _ => l.voiceWarm };

/// Profile: language, voice, nudge limits, privacy (export, delete), disclaimer, demo tools.
class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = L.of(context);
    final app = ref.watch(appProvider);
    final n = ref.read(appProvider.notifier);
    final me = app.me;
    final settings = me.m('settings');
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(Pk.pad, 8, Pk.pad, 40),
          children: [
            Align(alignment: Alignment.centerLeft, child: IconButton(onPressed: () => context.pop(), icon: const Icon(Icons.arrow_back, color: Pk.bone), tooltip: MaterialLocalizations.of(context).backButtonTooltip)),
            Row(
              children: [
                InitialTile(me.s('display_name', '?'), size: 54, highlight: true),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(me.s('display_name'), style: Pk.text(24, w: FontWeight.w600, h: 1.15)),
                      const SizedBox(height: 2),
                      Text([me.sn('occupation'), me.sn('city')].whereType<String>().join(' · '), style: Pk.text(13.5, c: Pk.muted)),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            _Section(l.language, Wrap(spacing: 8, children: [for (final e in languageNames.entries) PChip(label: e.value, selected: app.language == e.key, onTap: () => n.setLanguage(e.key))])),
            _Section(l.mascotVoice, Wrap(spacing: 8, children: [for (final v in voices) PChip(label: voiceLabel(l, v), selected: me.s('mascot_voice', 'warm') == v, onTap: () => n.setVoice(v))])),
            _Section(
              l.nudgesTitle,
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(l.nudgesPerDay, style: Pk.text(14, c: Pk.muted)),
                  const SizedBox(height: 8),
                  Row(children: [for (final v in const [0, 1, 2]) Padding(padding: const EdgeInsets.only(right: 8), child: PChip(label: '$v', selected: settings.i('nudge_daily_max', 2) == v, onTap: () => n.putSettings({'nudge_daily_max': v})))]),
                  const SizedBox(height: 12),
                  Row(children: [Expanded(child: Text(l.quietHours, style: Pk.text(14, c: Pk.muted))), Text('${settings.s('quiet_start', '22:00')} – ${settings.s('quiet_end', '08:00')}', style: Pk.num(14))]),
                ],
              ),
            ),
            _Section(
              l.linkedAccounts,
              Column(
                children: [
                  for (final a in app.accounts)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 5),
                      child: Row(children: [Expanded(child: Text(a.s('institution'), maxLines: 1, overflow: TextOverflow.ellipsis, style: Pk.text(14.5))), Text('·· ${a.s('last4')}', style: Pk.num(13, c: Pk.muted))]),
                    ),
                ],
              ),
            ),
            _Section(
              l.privacy,
              Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  GhostButton(
                    label: l.exportData,
                    icon: Icons.download_outlined,
                    dense: true,
                    onTap: () async {
                      try {
                        final data = await ref.read(apiProvider).get('/v1/export');
                        if (context.mounted) toast(context, l.exported(data.l('transactions').length));
                      } catch (_) {
                        if (context.mounted) toast(context, l.errorTitle);
                      }
                    },
                  ),
                  const SizedBox(height: 8),
                  GhostButton(label: l.deleteData, icon: Icons.delete_outline, dense: true, color: Pk.coral, onTap: () => _confirmDelete(context, ref)),
                ],
              ),
            ),
            _Section(l.disclaimerTitle, Text(l.disclaimerBody, style: Pk.text(14, c: Pk.muted, h: 1.45))),
            _Section(
              l.demoTools,
              Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  GhostButton(label: l.switchPersona, icon: Icons.swap_horiz, dense: true, onTap: () => context.push('/personas')),
                  const SizedBox(height: 8),
                  GhostButton(
                    label: l.injectSwiggy,
                    icon: Icons.bolt_outlined,
                    dense: true,
                    onTap: () async {
                      final res = await n.inject('swiggy_now');
                      if (!context.mounted) return;
                      if (res != null && res.m('sms').s('body').isNotEmpty) await _showBankSms(context, res);
                      if (context.mounted) context.go('/');
                    },
                  ),
                  const SizedBox(height: 8),
                  GhostButton(
                    label: l.startOver,
                    icon: Icons.restart_alt,
                    dense: true,
                    onTap: () async {
                      await n.signOutAndReset();
                      if (context.mounted) context.go('/welcome');
                    },
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _confirmDelete(BuildContext context, WidgetRef ref) {
    final l = L.of(context);
    showPocketSheet<void>(
      context,
      title: l.deleteData,
      builder: (ctx) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(l.deleteConfirm, style: Pk.text(15, c: Pk.muted, h: 1.45)),
          const SizedBox(height: 18),
          BlockButton(
            label: l.deleteData,
            color: Pk.coral,
            onColor: Pk.ink,
            onTap: () async {
              Navigator.of(ctx).pop();
              final ok = await ref.read(appProvider.notifier).deleteAccount();
              if (ok && context.mounted) context.go('/welcome');
            },
          ),
          const SizedBox(height: 10),
          GhostButton(label: l.cancel, onTap: () => Navigator.of(ctx).pop()),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section(this.title, this.child);
  final String title;
  final Widget child;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: Pk.gap),
      child: PCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [SectionLabel(title), const SizedBox(height: 12), child])),
    );
  }
}

/// Shows the synthetic bank SMS a demo transaction arrived as, and what the parser made of it.
/// Every figure on it comes from the server.
Future<void> _showBankSms(BuildContext context, Json res) {
  final l = L.of(context);
  final sms = res.m('sms');
  final txn = res.m('transaction');
  return showPocketSheet<void>(
    context,
    title: l.smsTitle,
    builder: (ctx) => Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(color: Pk.raised, border: Border.all(color: Pk.line)),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(sms.s('sender_id'), style: Pk.num(12, c: Pk.muted, ls: 0.4)),
              const SizedBox(height: 8),
              Text(sms.s('body'), style: Pk.num(13, w: FontWeight.w400, h: 1.5)),
            ],
          ),
        ),
        const Stitch(vertical: 16),
        SectionLabel(l.smsReadAs, color: Pk.lime),
        const SizedBox(height: 12),
        Row(
          children: [
            EmojiTile(txn.s('emoji', '•')),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(txn.s('merchant'), style: Pk.text(16, w: FontWeight.w600), maxLines: 1, overflow: TextOverflow.ellipsis),
                  const SizedBox(height: 2),
                  Text('${txn.s('category')} · ${txn.s('account')}', style: Pk.text(13, c: Pk.muted), maxLines: 1, overflow: TextOverflow.ellipsis),
                ],
              ),
            ),
            const SizedBox(width: 12),
            Text(txn.m('amount').s('exact'), style: Pk.num(18, w: FontWeight.w600)),
          ],
        ),
        const SizedBox(height: 16),
        Text(l.smsSynthetic, style: Pk.text(13, c: Pk.faint, h: 1.4)),
        const SizedBox(height: 18),
        BlockButton(label: l.smsSeeHome, onTap: () => Navigator.of(ctx).pop()),
      ],
    ),
  );
}
