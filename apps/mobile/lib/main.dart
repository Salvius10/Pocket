import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app.dart';
import 'core/api.dart';
import 'core/state.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  wakeServers();
  final prefs = await SharedPreferences.getInstance();
  final auth = AuthService(prefs);
  await auth.init();
  runApp(
    ProviderScope(
      overrides: [prefsProvider.overrideWithValue(prefs), authProvider.overrideWithValue(auth)],
      child: const PocketApp(),
    ),
  );
}
