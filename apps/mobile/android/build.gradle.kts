allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
// Some plugins still compile against an older Android API than their own AndroidX dependencies
// allow (flutter_pcm_sound 3.3.3 pins 33, and the build then fails AAR metadata checks). Compile
// every plugin against at least the app's API level. Registered before the block below so it runs
// ahead of the Android plugin's own afterEvaluate. Reflection keeps this file free of AGP imports.
val minPluginCompileSdk = 36
subprojects {
    afterEvaluate {
        val android = extensions.findByName("android") ?: return@afterEvaluate
        val getter = android.javaClass.methods.firstOrNull { it.name == "getCompileSdk" && it.parameterCount == 0 }
        val setter = android.javaClass.methods.firstOrNull { it.name == "setCompileSdk" && it.parameterCount == 1 }
        val current = getter?.invoke(android) as? Int
        if (setter != null && current != null && current < minPluginCompileSdk) {
            setter.invoke(android, minPluginCompileSdk)
            logger.lifecycle("pocket: ${project.name} compileSdk $current -> $minPluginCompileSdk")
        }
    }
}
subprojects {
    project.evaluationDependsOn(":app")
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
