import 'dart:math';

import 'package:dio/dio.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'config.dart';
import 'json.dart';

/// Demo sign-in. With Firebase config: anonymous auth behind "Try a demo persona".
/// Without it (local): a random device id sent as X-Dev-User.
class AuthService {
  AuthService(this._prefs);
  final SharedPreferences _prefs;
  static const _devKey = 'pocket.dev_user';
  bool _firebaseReady = false;

  Future<void> init() async {
    if (!Env.useFirebase) return;
    await Firebase.initializeApp(
      options: const FirebaseOptions(
        apiKey: Env.firebaseApiKey,
        appId: Env.firebaseAppId,
        projectId: Env.firebaseProjectId,
        authDomain: Env.firebaseAuthDomain,
        messagingSenderId: Env.firebaseSenderId,
      ),
    );
    _firebaseReady = true;
  }

  String get devUser {
    var id = _prefs.getString(_devKey);
    if (id == null) {
      final r = Random.secure();
      id = List.generate(16, (_) => r.nextInt(256).toRadixString(16).padLeft(2, '0')).join();
      _prefs.setString(_devKey, id);
    }
    return id;
  }

  bool get signedIn => _firebaseReady ? FirebaseAuth.instance.currentUser != null : _prefs.getBool('pocket.signed_in') ?? false;

  Future<void> signIn() async {
    if (_firebaseReady) {
      if (FirebaseAuth.instance.currentUser == null) await FirebaseAuth.instance.signInAnonymously();
    } else {
      devUser;
      await _prefs.setBool('pocket.signed_in', true);
    }
  }

  Future<void> signOut() async {
    if (_firebaseReady) {
      await FirebaseAuth.instance.signOut();
    } else {
      await _prefs.remove(_devKey);
      await _prefs.remove('pocket.signed_in');
    }
  }

  Future<String?> token() async => _firebaseReady ? await FirebaseAuth.instance.currentUser?.getIdToken() : null;

  Future<Map<String, String>> headers() async {
    final t = await token();
    return t != null ? {'Authorization': 'Bearer $t'} : {'X-Dev-User': devUser};
  }
}

class ApiError implements Exception {
  ApiError(this.message, {this.offline = false, this.status});
  final String message;
  final bool offline;
  final int? status;
  @override
  String toString() => message;
}

class Api {
  Api(this._auth)
      : _dio = Dio(BaseOptions(
          baseUrl: Env.apiBase,
          connectTimeout: const Duration(seconds: 8),
          receiveTimeout: const Duration(seconds: 40),
          headers: {'Content-Type': 'application/json'},
        ));
  final AuthService _auth;
  final Dio _dio;

  Future<Json> _send(String method, String path, {Object? body, Map<String, dynamic>? query}) async {
    try {
      final res = await _dio.request<dynamic>(
        path,
        data: body,
        queryParameters: query,
        options: Options(method: method, headers: await _auth.headers()),
      );
      final data = res.data;
      return data is Map ? Map<String, dynamic>.from(data) : <String, dynamic>{};
    } on DioException catch (e) {
      final status = e.response?.statusCode;
      if (status == null) throw ApiError('offline', offline: true);
      final data = e.response?.data;
      final detail = data is Map && data['detail'] is String ? data['detail'] as String : 'error';
      throw ApiError(detail, status: status);
    }
  }

  Future<Json> get(String path, {Map<String, dynamic>? query}) => _send('GET', path, query: query);
  Future<Json> post(String path, [Object? body]) => _send('POST', path, body: body ?? const <String, dynamic>{});
  Future<Json> put(String path, Object body) => _send('PUT', path, body: body);
  Future<Json> patch(String path, Object body) => _send('PATCH', path, body: body);
  Future<Json> delete(String path) => _send('DELETE', path);
}
