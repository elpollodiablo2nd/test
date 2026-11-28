package ai.mistral.mathaid;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * Minimal WebView-wrapper for the Math Aid web app (assets/index.html).
 *
 * NOTE: written in Java on purpose — the project has no Kotlin plugin, so a .kt
 * file would be silently skipped and the APK would crash at launch with
 * ClassNotFoundException (empty classes.dex).
 */
public class MainActivity extends Activity {

    private WebView webView;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        webView = new WebView(this);
        webView.getSettings().setJavaScriptEnabled(true);
        // localStorage (dagens % rigtige + historik) skal virke også på file://
        webView.getSettings().setDomStorageEnabled(true);
        webView.getSettings().setAllowFileAccess(true);
        webView.setWebViewClient(new WebViewClient()); // behold alt lokalt i appen
        setContentView(webView);

        webView.loadUrl("file:///android_asset/index.html");
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
