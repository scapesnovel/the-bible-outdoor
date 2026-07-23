package com.thebibleoutdoor.owner

import android.annotation.SuppressLint
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.core.view.WindowCompat
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout

class MainActivity : AppCompatActivity() {

    private lateinit var web: WebView
    private lateinit var swipe: SwipeRefreshLayout
    private var pageReady = false

    companion object {
        const val APP_URL = "https://scapesnovel.github.io/tbo-app/"
        // hosts allowed to stay INSIDE the app; everything else opens in the browser
        val INTERNAL_HOSTS = setOf(
            "scapesnovel.github.io",
            "raw.githubusercontent.com",
            "api.github.com"
        )
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        val splash = installSplashScreen()
        super.onCreate(savedInstanceState)
        // hold the native splash until the web app has painted (max ~2.5s)
        val bootAt = System.currentTimeMillis()
        splash.setKeepOnScreenCondition {
            !pageReady && System.currentTimeMillis() - bootAt < 2500
        }
        WindowCompat.setDecorFitsSystemWindows(window, true)
        window.statusBarColor = Color.parseColor("#0A1622") // matches app theme

        web = WebView(this)
        swipe = SwipeRefreshLayout(this).apply {
            addView(web)
            setColorSchemeColors(Color.parseColor("#CFA85E"))
            setProgressBackgroundColorSchemeColor(Color.parseColor("#10293A"))
            setOnRefreshListener { web.reload() }
        }
        setContentView(swipe)

        web.setBackgroundColor(Color.parseColor("#0A1622"))
        with(web.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true          // keeps your GitHub token saved (localStorage)
            databaseEnabled = true
            loadsImagesAutomatically = true
            useWideViewPort = true
            loadWithOverviewMode = true
        }

        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(
                view: WebView, request: WebResourceRequest
            ): Boolean {
                val url = request.url
                return if (url.host in INTERNAL_HOSTS) {
                    false // keep inside the app
                } else {
                    // YouTube links, Google fonts pages etc. -> real browser / YouTube app
                    startActivity(Intent(Intent.ACTION_VIEW, url))
                    true
                }
            }

            override fun onPageFinished(view: WebView, url: String) {
                swipe.isRefreshing = false
                pageReady = true
            }

            override fun onPageCommitVisible(view: WebView, url: String) {
                pageReady = true   // first paint — web splash takes over seamlessly
            }

            override fun onReceivedError(
                view: WebView, request: WebResourceRequest, error: WebResourceError
            ) {
                if (request.isForMainFrame) {
                    view.loadData(
                        """
                        <html><body style="background:#0a1622;color:#e9eff4;
                          font-family:sans-serif;display:flex;align-items:center;
                          justify-content:center;height:100vh;text-align:center">
                          <div>
                            <h2 style="color:#cfa85e">No connection</h2>
                            <p>Check your internet, then pull down to retry.</p>
                          </div>
                        </body></html>
                        """.trimIndent(),
                        "text/html", "utf-8"
                    )
                }
            }
        }

        // Android back button = go back inside the web app
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (web.canGoBack()) web.goBack() else finish()
            }
        })

        // only allow pull-to-refresh when the page is scrolled to the very top
        web.viewTreeObserver.addOnScrollChangedListener {
            swipe.isEnabled = web.scrollY == 0
        }

        if (savedInstanceState == null) web.loadUrl(APP_URL) else web.restoreState(savedInstanceState)
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        web.saveState(outState)
    }
}
