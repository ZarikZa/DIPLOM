package com.example.hhdiplom.activities;

import android.content.Intent;
import android.os.Bundle;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.example.hhdiplom.MainActivity;
import com.example.hhdiplom.R;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.ApiService;
import com.example.hhdiplom.models.CmVideoResponse;
import com.example.hhdiplom.models.LoginRequest;
import com.example.hhdiplom.models.TokenResponse;
import com.example.hhdiplom.models.UserProfile;
import com.google.android.material.textfield.TextInputEditText;
import com.google.android.material.textfield.TextInputLayout;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

public class LoginActivity extends AppCompatActivity {

    private TextInputEditText etUsername;
    private TextInputEditText etPassword;
    private TextInputLayout emailLayout;
    private TextInputLayout passwordLayout;
    private Button btnLogin;
    private Button btnRegister;
    private TextView tvForgotPassword;

    private ApiService apiService;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_login);

        ApiClient.init(this);
        apiService = ApiClient.getApiService();

        initViews();
        setupListeners();
        setLoginLoading(false);

        if (ApiClient.isLoggedIn()) {
            setLoginLoading(true);
            autoLoginRoute();
        }
    }

    private void initViews() {
        emailLayout = findViewById(R.id.emailLayout);
        passwordLayout = findViewById(R.id.passwordLayout);
        etUsername = findViewById(R.id.etUsername);
        etPassword = findViewById(R.id.etPassword);
        btnLogin = findViewById(R.id.btnLogin);
        btnRegister = findViewById(R.id.btnRegister);
        tvForgotPassword = findViewById(R.id.tvForgotPassword);
    }

    private void setupListeners() {
        btnLogin.setOnClickListener(v -> {
            emailLayout.setError(null);
            passwordLayout.setError(null);

            String username = etUsername.getText() == null ? "" : etUsername.getText().toString().trim();
            String password = etPassword.getText() == null ? "" : etPassword.getText().toString().trim();

            boolean hasError = false;
            if (username.isEmpty()) {
                emailLayout.setError(getString(R.string.login_error_email_required));
                hasError = true;
            } else if (!android.util.Patterns.EMAIL_ADDRESS.matcher(username).matches()) {
                emailLayout.setError(getString(R.string.login_error_email_invalid));
                hasError = true;
            }

            if (password.isEmpty()) {
                passwordLayout.setError(getString(R.string.login_error_password_required));
                hasError = true;
            } else if (password.length() < 6) {
                passwordLayout.setError(getString(R.string.login_error_password_min));
                hasError = true;
            }

            if (!hasError) {
                setLoginLoading(true);
                loginUser(username, password);
            }
        });

        tvForgotPassword.setOnClickListener(v -> {
            startActivity(new Intent(LoginActivity.this, PasswordResetRequestActivity.class));
            overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
        });

        btnRegister.setOnClickListener(v -> {
            startActivity(new Intent(LoginActivity.this, RegisterActivity.class));
            overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
        });
    }

    private void setLoginLoading(boolean isLoading) {
        btnLogin.setEnabled(!isLoading);
        btnRegister.setEnabled(!isLoading);
        etUsername.setEnabled(!isLoading);
        etPassword.setEnabled(!isLoading);
        btnLogin.setText(isLoading ? getString(R.string.login_button_loading) : getString(R.string.login_button));
    }

    private void autoLoginRoute() {
        String override = ApiClient.getEmployeeRoleOverride();
        if (override != null && override.toLowerCase().contains("content")) {
            startActivity(new Intent(LoginActivity.this, com.example.hhdiplom.CmMainActivity.class));
            finish();
            return;
        }

        apiService.getUserProfile().enqueue(new Callback<UserProfile>() {
            @Override
            public void onResponse(Call<UserProfile> call, Response<UserProfile> response) {
                if (response.isSuccessful() && response.body() != null) {
                    ApiClient.saveUserInfo(response.body());
                    goToRoleBasedMain(response.body());
                } else {
                    fallbackCheckCmEndpoint();
                }
            }

            @Override
            public void onFailure(Call<UserProfile> call, Throwable t) {
                fallbackCheckCmEndpoint();
            }
        });
    }

    private void goToRoleBasedMain(UserProfile profile) {
        String role = profile.getEmployeeRole() == null ? "" : profile.getEmployeeRole().toLowerCase();

        if (role.contains("content")) {
            ApiClient.saveEmployeeRoleOverride("content_manager");
            startActivity(new Intent(LoginActivity.this, com.example.hhdiplom.CmMainActivity.class));
            finish();
            return;
        }

        fallbackCheckCmEndpoint();
    }

    private void fallbackCheckCmEndpoint() {
        apiService.getContentManagerVideos(1).enqueue(new Callback<CmVideoResponse>() {
            @Override
            public void onResponse(Call<CmVideoResponse> call, Response<CmVideoResponse> response) {
                if (response.isSuccessful()) {
                    ApiClient.saveEmployeeRoleOverride("content_manager");
                    startActivity(new Intent(LoginActivity.this, com.example.hhdiplom.CmMainActivity.class));
                } else {
                    startActivity(new Intent(LoginActivity.this, MainActivity.class));
                }
                finish();
            }

            @Override
            public void onFailure(Call<CmVideoResponse> call, Throwable t) {
                startActivity(new Intent(LoginActivity.this, MainActivity.class));
                finish();
            }
        });
    }

    private void loginUser(String username, String password) {
        LoginRequest loginRequest = new LoginRequest(username, password);

        apiService.login(loginRequest).enqueue(new Callback<TokenResponse>() {
            @Override
            public void onResponse(Call<TokenResponse> call, Response<TokenResponse> response) {
                if (response.isSuccessful() && response.body() != null) {
                    TokenResponse tokenResponse = response.body();

                    ApiClient.saveTokens(
                            tokenResponse.getAccessToken(),
                            tokenResponse.getRefreshToken(),
                            tokenResponse.getUserId(),
                            tokenResponse.getUserType()
                    );

                    loadAndSaveUserProfile(tokenResponse.getAccessToken());
                } else {
                    setLoginLoading(false);
                    handleLoginError(response.code());
                }
            }

            @Override
            public void onFailure(Call<TokenResponse> call, Throwable t) {
                setLoginLoading(false);
                String message = t.getMessage() == null ? getString(R.string.login_network_unknown) : t.getMessage();
                Toast.makeText(LoginActivity.this,
                        getString(R.string.error_network_with_message, message),
                        Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void loadAndSaveUserProfile(String accessToken) {
        OkHttpClient client = new OkHttpClient.Builder()
                .addInterceptor(chain -> {
                    Request original = chain.request();
                    Request request = original.newBuilder()
                            .header("Authorization", "Bearer " + accessToken)
                            .build();
                    return chain.proceed(request);
                })
                .build();

        Retrofit tempRetrofit = new Retrofit.Builder()
                .baseUrl(ApiClient.BASE_URL)
                .client(client)
                .addConverterFactory(GsonConverterFactory.create())
                .build();

        ApiService tempService = tempRetrofit.create(ApiService.class);

        tempService.getUserProfile().enqueue(new Callback<UserProfile>() {
            @Override
            public void onResponse(Call<UserProfile> call, Response<UserProfile> response) {
                if (response.isSuccessful() && response.body() != null) {
                    ApiClient.saveUserInfo(response.body());

                    goToRoleBasedMain(response.body(), tempService);
                } else {
                    setLoginLoading(false);
                }
            }

            @Override
            public void onFailure(Call<UserProfile> call, Throwable t) {
                setLoginLoading(false);
                String message = t.getMessage() == null ? getString(R.string.login_network_unknown) : t.getMessage();
            }
        });
    }

    private void goToRoleBasedMain(UserProfile profile, ApiService serviceWithAuth) {
        String role = profile.getEmployeeRole() == null ? "" : profile.getEmployeeRole().toLowerCase();
        if (role.contains("content")) {
            ApiClient.saveEmployeeRoleOverride("content_manager");
            startActivity(new Intent(LoginActivity.this, com.example.hhdiplom.CmMainActivity.class));
            finish();
            return;
        }

        serviceWithAuth.getContentManagerVideos(1).enqueue(new Callback<CmVideoResponse>() {
            @Override
            public void onResponse(Call<CmVideoResponse> call, Response<CmVideoResponse> response) {
                if (response.isSuccessful()) {
                    ApiClient.saveEmployeeRoleOverride("content_manager");
                    startActivity(new Intent(LoginActivity.this, com.example.hhdiplom.CmMainActivity.class));
                } else {
                    startActivity(new Intent(LoginActivity.this, MainActivity.class));
                }
                finish();
            }

            @Override
            public void onFailure(Call<CmVideoResponse> call, Throwable t) {
                startActivity(new Intent(LoginActivity.this, MainActivity.class));
                finish();
            }
        });
    }

    private void handleLoginError(int errorCode) {
        switch (errorCode) {
            case 401:
                passwordLayout.setError(getString(R.string.login_invalid_credentials));
                break;
            case 404:
                emailLayout.setError(getString(R.string.login_user_not_found));
                break;
            case 500:
                Toast.makeText(this, getString(R.string.login_server_error), Toast.LENGTH_LONG).show();
                break;
            default:
                Toast.makeText(this, getString(R.string.login_auth_error_code, errorCode), Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    public void onBackPressed() {
        super.onBackPressed();
        overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
    }
}
