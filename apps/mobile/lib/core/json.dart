/// The API speaks snake_case JSON. These helpers read it safely without a model class per shape.
typedef Json = Map<String, dynamic>;

extension JsonX on Map<String, dynamic> {
  Json m(String key) {
    final v = this[key];
    return v is Map ? Map<String, dynamic>.from(v) : <String, dynamic>{};
  }

  List<Json> l(String key) {
    final v = this[key];
    if (v is! List) return const [];
    return [for (final e in v) if (e is Map) Map<String, dynamic>.from(e)];
  }

  List<String> strings(String key) {
    final v = this[key];
    return v is List ? [for (final e in v) '$e'] : const [];
  }

  String s(String key, [String fallback = '']) {
    final v = this[key];
    return v == null ? fallback : '$v';
  }

  String? sn(String key) {
    final v = this[key];
    return v == null ? null : '$v';
  }

  int i(String key, [int fallback = 0]) {
    final v = this[key];
    return v is num ? v.toInt() : fallback;
  }

  bool b(String key) => this[key] == true;

  /// `display` of a Money object at [key], e.g. "₹1,23,456".
  String money(String key) => m(key).s('display', '—');

  int paise(String key) => m(key).i('paise');
}
