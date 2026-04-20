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
import com.example.hhdiplom.fragments.ProfileFragment;
import com.example.hhdiplom.fragments.cm.CmUploadSelectVacancyFragment;
import com.example.hhdiplom.fragments.cm.CmVideosFragment;
import com.example.hhdiplom.utils.ThemePrefs;
import com.google.android.material.bottomnavigation.BottomNavigationView;

public class CmMainActivity extends AppCompatActivity {

    private BottomNavigationView bottomNavigationView;
    private FrameLayout fragmentContainer;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        ThemePrefs.applySavedTheme(this);
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_cm_main);

        ApiClient.init(this);

        fragmentContainer = findViewById(R.id.fragmentContainer);
        bottomNavigationView = findViewById(R.id.bottomNavigationView);

        TokenManager.checkTokenOnAppStart(this, new TokenManager.TokenRefreshCallback() {
            @Override
            public void onTokenRefreshed() {
                runOnUiThread(CmMainActivity.this::setupNavigation);
            }

            @Override
            public void onTokenRefreshFailed(String error) {
                runOnUiThread(() -> {
                    ApiClient.clearTokens();
                    Toast.makeText(CmMainActivity.this,
                            getString(R.string.session_expired_login_again),
                            Toast.LENGTH_LONG).show();
                    startActivity(new Intent(CmMainActivity.this, LoginActivity.class));
                    finish();
                });
            }
        });

        setupNavigation();

        Toast.makeText(this,
                getString(R.string.cm_logged_as, com.example.hhdiplom.utils.RoleUtils.getDebugRoleString()),
                Toast.LENGTH_SHORT).show();

        if (savedInstanceState == null) {
            loadFragment(new CmVideosFragment());
            bottomNavigationView.setSelectedItemId(R.id.nav_cm_videos);
        }
    }

    private void setupNavigation() {
        bottomNavigationView.getMenu().clear();
        bottomNavigationView.inflateMenu(R.menu.bottom_nav_menu_cm_only);

        bottomNavigationView.setOnNavigationItemSelectedListener(item -> {
            int itemId = item.getItemId();
            Fragment selectedFragment = null;

            if (itemId == R.id.nav_cm_videos) {
                selectedFragment = new CmVideosFragment();
            } else if (itemId == R.id.nav_cm_upload) {
                selectedFragment = new CmUploadSelectVacancyFragment();
            } else if (itemId == R.id.nav_cm_profile) {
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
