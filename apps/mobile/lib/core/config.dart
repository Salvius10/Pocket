import 'package:flutter/foundation.dart' show kIsWeb;

/// Build-time configuration (`--dart-define`). No secret ever goes here: the Gemini key lives
/// only on the agent service. Firebase web config values are public identifiers, not secrets.
abstract final class Env {
  static const _apiBase = String.fromEnvironment('API_BASE', defaultValue: 'auto');
  static const _agentBase = String.fromEnvironment('AGENT_BASE', defaultValue: 'auto');

  /// core-api address. `auto` (the default) means "the machine that served this page, port 8080",
  /// so one web build works on localhost, over a hotspot and through a tunnel without rebuilding.
  /// Deployed builds pass the Cloud Run URLs explicitly.
  static String get apiBase => _resolve(_apiBase, 8080);
  static String get agentBase => _resolve(_agentBase, 8081);

  static String _resolve(String value, int port) {
    if (value != 'auto') return value;
    if (kIsWeb && Uri.base.host.isNotEmpty) {
      return '${Uri.base.scheme == 'https' ? 'https' : 'http'}://${Uri.base.host}:$port';
    }
    return 'http://localhost:$port';
  }

  static const firebaseApiKey = String.fromEnvironment('FIREBASE_API_KEY');
  static const firebaseAppId = String.fromEnvironment('FIREBASE_APP_ID');
  static const firebaseProjectId = String.fromEnvironment('FIREBASE_PROJECT_ID');
  static const firebaseAuthDomain = String.fromEnvironment('FIREBASE_AUTH_DOMAIN');
  static const firebaseSenderId = String.fromEnvironment('FIREBASE_MESSAGING_SENDER_ID');

  /// Without Firebase config the app signs in with a local dev id (works only against AUTH_MODE=dev).
  static bool get useFirebase => firebaseApiKey.isNotEmpty && firebaseAppId.isNotEmpty && firebaseProjectId.isNotEmpty;

  static String get agentWs => '${agentBase.replaceFirst(RegExp('^http'), 'ws')}/v1/live';
}
