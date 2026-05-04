package com.example.hhdiplom;

import android.content.Intent;
import android.os.Bundle;
import android.widget.FrameLayout;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.fragment.app.Fragment;
import androidx.fragment.app.FragmentTransaction;

import com.example.hhdiplom.activities.LoginActivity;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.TokenManager;
import com.example.hhdiplom.fragments.ChatsFragment;
import com.example.hhdiplom.fragments.FeedVideoFragment;
import com.example.hhdiplom.fragments.ProfileFragment;
import com.example.hhdiplom.fragments.ResponsesFragment;
import com.example.hhdiplom.fragments.VacanciesFragment;
import com.example.hhdiplom.notifications.AppNotificationCoordinator;
import com.example.hhdiplom.utils.ThemePrefs;
import com.google.android.material.bottomnavigation.BottomNavigationView;

public class MainActivity extends AppCompatActivity {

    private BottomNavigationView bottomNavigationView;
    private FrameLayout fragmentContainer;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        ThemePrefs.applySavedTheme(this);
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        ApiClient.init(this);
        AppNotificationCoordinator.requestPermissionIfNeeded(this);
        AppNotificationCoordinator.schedule(this);

        fragmentContainer = findViewById(R.id.fragmentContainer);
        bottomNavigationView = findViewById(R.id.bottomNavigationView);

        TokenManager.checkTokenOnAppStart(this, new TokenManager.TokenRefreshCallback() {
            @Override
            public void onTokenRefreshed() {
                runOnUiThread(MainActivity.this::setupNavigation);
            }

            @Override
            public void onTokenRefreshFailed(String error) {
                runOnUiThread(() -> {
                    AppNotificationCoordinator.onUserLoggedOut(MainActivity.this);
                    ApiClient.clearTokens();
                    Toast.makeText(MainActivity.this,
                            getString(R.string.session_expired_login_again),
                            Toast.LENGTH_LONG).show();
                    startActivity(new Intent(MainActivity.this, LoginActivity.class));
                    finish();
                });
            }
        });

        setupNavigation();

        if (savedInstanceState == null) {
            loadFragment(new VacanciesFragment());
            bottomNavigationView.setSelectedItemId(R.id.nav_search);
        }
    }

    private void setupNavigation() {
        bottomNavigationView.getMenu().clear();
        bottomNavigationView.inflateMenu(R.menu.bottom_nav_menu);

        bottomNavigationView.setOnNavigationItemSelectedListener(item -> {
            Fragment selectedFragment = null;
            int itemId = item.getItemId();

            if (itemId == R.id.nav_search) {
                selectedFragment = new VacanciesFragment();
            } else if (itemId == R.id.nav_responses) {
                selectedFragment = new ResponsesFragment();
            } else if (itemId == R.id.nav_feed) {
                selectedFragment = new FeedVideoFragment();
            } else if (itemId == R.id.nav_messages) {
                selectedFragment = new ChatsFragment();
            } else if (itemId == R.id.nav_profile) {
                selectedFragment = new ProfileFragment();
            }

            if (selectedFragment != null) {
                loadFragment(selectedFragment);
                return true;
            }
            return false;
        });
    }

    private void loadFragment(Fragment fragment) {
        FragmentTransaction transaction = getSupportFragmentManager().beginTransaction();
        transaction.replace(R.id.fragmentContainer, fragment);
        transaction.commit();
    }
}
