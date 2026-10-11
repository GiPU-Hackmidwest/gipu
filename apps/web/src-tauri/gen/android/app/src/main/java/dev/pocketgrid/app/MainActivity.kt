package dev.pocketgrid.app

import android.os.Bundle
import android.view.View
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

// Matches the page background in apps/web/src/style.css; the interface is light-only.
private const val PAGE_BACKGROUND = 0xFFF1F5F3.toInt()

class MainActivity : TauriActivity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    // Dark system-bar icons in both system themes, because the page itself has no dark mode.
    enableEdgeToEdge(
      statusBarStyle = SystemBarStyle.light(PAGE_BACKGROUND, PAGE_BACKGROUND),
      navigationBarStyle = SystemBarStyle.light(PAGE_BACKGROUND, PAGE_BACKGROUND),
    )
    super.onCreate(savedInstanceState)

    // Keep the webview clear of the status bar, navigation bar, cutouts and keyboard.
    // Doing this natively avoids relying on the WebView version's safe-area support.
    val content = findViewById<View>(android.R.id.content)
    content.setBackgroundColor(PAGE_BACKGROUND)
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
}
