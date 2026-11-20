import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import 'core/state.dart';
import 'core/theme.dart';
import 'features/collab/collab_screen.dart';
import 'features/onboarding/onboarding_screens.dart';
import 'features/profile/profile_screen.dart';
import 'features/report/report_screen.dart';
import 'features/shell/shell.dart';
import 'l10n/app_localizations.dart';

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: '/',
    redirect: (context, state) {
      final app = ref.read(appProvider);
      final path = state.matchedLocation;
      const open = {'/welcome'};
      if (!app.signedIn) return open.contains(path) ? null : '/welcome';
      // Signed in but nothing linked yet: finish onboarding before the tabs.
      if (path == '/welcome') return app.linked ? '/' : '/talk';
      if (path == '/' && app.bundle != null && !app.linked) return '/personas';
      return null;
    },
    routes: [
      GoRoute(path: '/', builder: (_, _) => const Shell()),
      GoRoute(path: '/welcome', builder: (_, _) => const WelcomeScreen()),
      GoRoute(path: '/talk', builder: (_, _) => const TalkScreen()),
      GoRoute(path: '/personas', builder: (_, _) => const PersonaScreen()),
      GoRoute(path: '/building', builder: (_, _) => const BuildingScreen()),
      GoRoute(path: '/profile', builder: (_, _) => const ProfileScreen()),
      GoRoute(path: '/report', builder: (_, _) => const ReportScreen()),
      GoRoute(path: '/group/:id', builder: (_, s) => GroupScreen(groupId: s.pathParameters['id']!)),
    ],
  );
});

/// Pocket's strings plus Material's, Cupertino's and the base widgets' own strings.
///
/// Not `L.localizationsDelegates`: the generated list still names the old delegates from
/// `flutter_localizations`, which produce a different `MaterialLocalizations` type from the one
/// `material_ui` widgets look up. English then falls back to the built-in default, but in Hindi
/// and Tamil every `MaterialLocalizations.of(context)` (a back button's tooltip, a sheet's close
/// label, a text field's menu) is null and the screen fails to draw.
const pocketLocalizationsDelegates = <LocalizationsDelegate<dynamic>>[L.delegate, ...GlobalMaterialLocalizations.delegates];

class PocketApp extends ConsumerWidget {
  const PocketApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final language = ref.watch(appProvider.select((s) => s.language));
    final router = ref.watch(routerProvider);
    // Re-run redirects when sign-in or link state changes.
    ref.listen(appProvider.select((s) => (s.signedIn, s.linked, s.bundle != null)), (_, _) => router.refresh());
    return MaterialApp.router(
      title: 'Pocket',
      debugShowCheckedModeBanner: false,
      theme: pocketTheme(),
      locale: Locale(language),
      supportedLocales: L.supportedLocales,
      localizationsDelegates: pocketLocalizationsDelegates,
      routerConfig: router,
      builder: (context, child) => _PhoneFrame(child: child ?? const SizedBox.shrink()),
    );
  }
}

/// On a laptop the web build sits in a phone-width column, so judges see the app as designed.
class _PhoneFrame extends StatelessWidget {
  const _PhoneFrame({required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    if (width < 560) return child;
    return Material(
      color: const Color(0xFF070806),
      child: Stack(
        children: [
          Positioned.fill(child: CustomPaint(painter: _BackdropGrid())),
          if (width > 1040)
            Positioned(
              left: 48,
              bottom: 44,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('POCKET', style: Pk.text(84, w: FontWeight.w700, c: Pk.surface, h: 0.9, ls: -3)),
                  const SizedBox(height: 10),
                  Text('DATA, NOT ADVICE · SYNTHETIC DEMO', style: Pk.label(c: Pk.faint)),
                ],
              ),
            ),
          Center(
            child: Container(
              width: 440,
              margin: const EdgeInsets.symmetric(vertical: 18),
              clipBehavior: Clip.antiAlias,
              decoration: BoxDecoration(color: Pk.ink, borderRadius: BorderRadius.circular(14), border: Border.all(color: Pk.lineStrong)),
              child: MediaQuery(data: MediaQuery.of(context).copyWith(size: Size(440, MediaQuery.sizeOf(context).height - 36)), child: child),
            ),
          ),
        ],
      ),
    );
  }
}

class _BackdropGrid extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()..color = const Color(0xFF12130F)..strokeWidth = 1;
    for (double x = 0; x < size.width; x += 44) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), p);
    }
    for (double y = 0; y < size.height; y += 44) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), p);
    }
  }

  @override
  bool shouldRepaint(_BackdropGrid old) => false;
}
