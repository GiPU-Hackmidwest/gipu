package dev.pocketgrid.app

import android.content.res.Configuration
import android.os.Bundle
import android.view.View
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

// Matches the shared web canvas in apps/web/src/style.css.
private const val LIGHT_BACKGROUND = 0xFFF4F6F8.toInt()
private const val DARK_BACKGROUND = 0xFF202328.toInt()

class MainActivity : TauriActivity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    val background = configureSystemBars(resources.configuration)
    super.onCreate(savedInstanceState)

    // Keep the webview clear of the status bar, navigation bar, cutouts and keyboard.
    // Doing this natively avoids relying on the WebView version's safe-area support.
    val content = findViewById<View>(android.R.id.content)
    content.setBackgroundColor(background)
    ViewCompat.setOnApplyWindowInsetsListener(content) { view, insets ->
      val bars = insets.getInsets(
        WindowInsetsCompat.Type.systemBars() or
          WindowInsetsCompat.Type.displayCutout() or
          WindowInsetsCompat.Type.ime()
      )
      view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
      WindowInsetsCompat.CONSUMED
    }
  }

  override fun onConfigurationChanged(newConfig: Configuration) {
    super.onConfigurationChanged(newConfig)
    // uiMode is handled by this activity rather than recreating the webview.
    val background = configureSystemBars(newConfig)
    findViewById<View>(android.R.id.content).setBackgroundColor(background)
  }

  private fun configureSystemBars(configuration: Configuration): Int {
    val dark = configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK == Configuration.UI_MODE_NIGHT_YES
    val background = if (dark) DARK_BACKGROUND else LIGHT_BACKGROUND
    val style = if (dark) SystemBarStyle.dark(background) else SystemBarStyle.light(background, background)
    enableEdgeToEdge(statusBarStyle = style, navigationBarStyle = style)
    return background
  }
}
