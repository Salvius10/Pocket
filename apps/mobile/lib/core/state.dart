import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';
import 'json.dart';

final prefsProvider = Provider<SharedPreferences>((ref) => throw UnimplementedError('overridden in main'));
final authProvider = Provider<AuthService>((ref) => throw UnimplementedError('overridden in main'));
final apiProvider = Provider<Api>((ref) => Api(ref.watch(authProvider)));

/// Which tab is showing. 0 Home · 1 Money · 2 Mascot · 3 Plan · 4 Collab.
class TabNotifier extends Notifier<int> {
  @override
  int build() => 0;
  void go(int index) => state = index;
}

final tabProvider = NotifierProvider<TabNotifier, int>(TabNotifier.new);

/// Offline cache: the last sync bundle, kept on the phone.
///
/// The app renders from this copy and never computes a total itself. Offline it shows these
/// numbers with their "as of" time. (Behind this small interface so drift can replace it.)
class SnapshotStore {
  SnapshotStore(this._prefs);
  final SharedPreferences _prefs;
  static const _key = 'pocket.snapshot.v1';

  Json? read() {
    final raw = _prefs.getString(_key);
    if (raw == null) return null;
    try {
      return Map<String, dynamic>.from(jsonDecode(raw) as Map);
    } catch (_) {
      return null;
    }
  }

  Future<void> write(Json bundle) => _prefs.setString(_key, jsonEncode(bundle));
  Future<void> clear() => _prefs.remove(_key);
}

class AppState {
  const AppState({this.bundle, this.loading = false, this.offline = false, this.error, this.signedIn = false, this.language = 'en'});
  final Json? bundle;
  final bool loading;
  final bool offline;
  final String? error;
  final bool signedIn;
  final String language;

  bool get linked => bundle?.b('linked') ?? false;
  Json get me => bundle?.m('me') ?? const {};
  Json get summary => bundle?.m('summary') ?? const {};
  Json get home => bundle?.m('home') ?? const {};
  List<Json> get insights => bundle?.l('insights') ?? const [];
  Json get pulse => bundle?.m('pulse') ?? const {};
  List<Json> get groups => bundle?.l('groups') ?? const [];
  List<Json> get nudges => bundle?.l('nudges') ?? const [];
  List<Json> get proposals => bundle?.l('proposals') ?? const [];
  List<Json> get transactions => bundle?.l('transactions') ?? const [];
  List<Json> get accounts => bundle?.l('accounts') ?? const [];
  List<Json> get categories => bundle?.l('categories') ?? const [];
  DateTime? get asOf => DateTime.tryParse(bundle?.s('as_of') ?? '')?.toLocal();

  AppState copy({Json? bundle, bool? loading, bool? offline, String? error, bool clearError = false, bool? signedIn, String? language, bool clearBundle = false}) {
    return AppState(
      bundle: clearBundle ? null : bundle ?? this.bundle,
      loading: loading ?? this.loading,
      offline: offline ?? this.offline,
      error: clearError ? null : error ?? this.error,
      signedIn: signedIn ?? this.signedIn,
      language: language ?? this.language,
    );
  }
}

class AppNotifier extends Notifier<AppState> {
  late final SnapshotStore _store = SnapshotStore(ref.read(prefsProvider));
  Api get _api => ref.read(apiProvider);
  static const _langKey = 'pocket.language';

  @override
  AppState build() {
    final prefs = ref.read(prefsProvider);
    final cached = _store.read();
    final signedIn = ref.read(authProvider).signedIn;
    final lang = cached?.m('me').sn('language') ?? prefs.getString(_langKey) ?? 'en';
    // Start from the cache so the app opens instantly, and without a network.
    if (signedIn) Future.microtask(sync);
    return AppState(bundle: signedIn ? cached : null, signedIn: signedIn, language: lang, loading: signedIn && cached == null);
  }

  Future<void> sync() async {
    if (!state.signedIn) return;
    state = state.copy(loading: state.bundle == null, clearError: true);
    try {
      final bundle = await _api.get('/v1/sync');
      await _store.write(bundle);
      state = state.copy(bundle: bundle, loading: false, offline: false, language: bundle.m('me').sn('language') ?? state.language);
    } on ApiError catch (e) {
      state = state.copy(loading: false, offline: e.offline, error: e.offline ? null : e.message);
    }
  }

  Future<void> setLanguage(String lang) async {
    await ref.read(prefsProvider).setString(_langKey, lang);
    state = state.copy(language: lang);
    if (state.signedIn) {
      await _guard(() => _api.patch('/v1/me', {'language': lang}));
      await sync();
    }
  }

  Future<void> signIn() async {
    await ref.read(authProvider).signIn();
    state = state.copy(signedIn: true, loading: true);
    await _guard(() => _api.patch('/v1/me', {'language': state.language}));
    await sync();
  }

  Future<void> setVoice(String voice) async {
    await _guard(() => _api.patch('/v1/me', {'mascot_voice': voice}));
    _patchMe({'mascot_voice': voice});
  }

  Future<bool> link(String personaId) async {
    state = state.copy(loading: true, clearError: true);
    final ok = await _guard(() => _api.post('/v1/onboarding/link', {'persona_id': personaId}));
    await sync();
    return ok != null;
  }

  Future<void> signOutAndReset() async {
    await ref.read(authProvider).signOut();
    await _store.clear();
    state = AppState(language: state.language);
  }

  Future<bool> deleteAccount() async {
    final ok = await _guard(() => _api.delete('/v1/me'));
    if (ok == null) return false;
    await signOutAndReset();
    return true;
  }

  /// The only way a suggested change runs: the user tapped Confirm.
  Future<bool> acceptProposal(String id) async {
    final ok = await _guard(() => _api.post('/v1/proposals/$id/accept'));
    await sync();
    return ok != null;
  }

  Future<void> declineProposal(String id) async {
    await _guard(() => _api.post('/v1/proposals/$id/decline'));
    await sync();
  }

  Future<Json?> compose(String? instruction) async {
    final out = await _guard(() => _api.post('/v1/home/compose', {'instruction': instruction}));
    if (out != null) applyHome(out);
    return out;
  }

  Future<void> manualLayout(List<Json> widgets) async {
    final out = await _guard(() => _api.put('/v1/home/manual', {'widgets': widgets}));
    if (out != null) applyHome(out);
  }

  Future<void> resetLayout() async {
    final out = await _guard(() => _api.post('/v1/home/reset'));
    if (out != null) applyHome(out);
  }

  void applyHome(Json home) {
    final b = state.bundle;
    if (b == null) return;
    final next = {...b, 'home': home};
    _store.write(next);
    state = state.copy(bundle: next);
  }

  Future<void> dismissNudge(String id) async {
    final b = state.bundle;
    if (b != null) {
      state = state.copy(bundle: {...b, 'nudges': [for (final n in b.l('nudges')) if (n.s('id') != id) n]});
    }
    await _guard(() => _api.post('/v1/nudges/$id/dismiss'));
  }

  Future<void> dismissInsight(String id) async {
    await _guard(() => _api.post('/v1/insights/$id/dismiss'));
    await sync();
  }

  Future<bool> putSettings(Json body) async {
    final out = await _guard(() => _api.put('/v1/settings', body));
    if (out != null) _patchMe(out);
    return out != null;
  }

  Future<bool> addTransaction(Json body) async {
    final ok = await _guard(() => _api.post('/v1/transactions', body));
    await sync();
    return ok != null;
  }

  Future<bool> recategorise(String txnId, String categoryId) async {
    final ok = await _guard(() => _api.patch('/v1/transactions/$txnId', {'category_id': categoryId}));
    await sync();
    return ok != null;
  }

  Future<bool> inject(String preset) async {
    final ok = await _guard(() => _api.post('/v1/demo/inject', {'preset': preset}));
    await sync();
    return ok != null;
  }

  Future<bool> send(String method, String path, [Json? body]) async {
    final ok = await _guard(() => switch (method) {
          'POST' => _api.post(path, body),
          'PUT' => _api.put(path, body ?? const {}),
          'PATCH' => _api.patch(path, body ?? const {}),
          'DELETE' => _api.delete(path),
          _ => _api.get(path),
        });
    return ok != null;
  }

  void _patchMe(Json fields) {
    final b = state.bundle;
    if (b == null) return;
    state = state.copy(bundle: {...b, 'me': {...b.m('me'), ...fields}});
  }

  Future<Json?> _guard(Future<Json> Function() call) async {
    try {
      final out = await call();
      if (state.offline) state = state.copy(offline: false);
      return out;
    } on ApiError catch (e) {
      state = state.copy(offline: e.offline, error: e.offline ? null : e.message, loading: false);
      return null;
    }
  }
}

final appProvider = NotifierProvider<AppNotifier, AppState>(AppNotifier.new);

/// One-off reads that are not in the sync bundle (lists behind a tab).
final fetchProvider = FutureProvider.autoDispose.family<Json, String>((ref, path) async {
  ref.watch(appProvider.select((s) => s.bundle?.s('cursor')));
  return ref.read(apiProvider).get(path);
});
