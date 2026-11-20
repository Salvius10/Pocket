import 'dart:io';

/// Shared fixtures live in the repo's data/fixtures (the Python tests read the same files).
/// POCKET_FIXTURES overrides the location when the tests run from a build mirror.
String fixturePath(String name) {
  final dir = Platform.environment['POCKET_FIXTURES'] ?? '../../data/fixtures';
  return '$dir/$name';
}
