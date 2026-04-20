package com.example.hhdiplom.activities;

import android.app.DatePickerDialog;
import android.content.Intent;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;

import com.example.hhdiplom.MainActivity;
import com.example.hhdiplom.R;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.ApiService;
import com.example.hhdiplom.models.RegisterRequest;
import com.example.hhdiplom.models.TokenResponse;
import com.example.hhdiplom.utils.ProfanityValidator;
import com.google.android.material.textfield.TextInputEditText;
import com.google.android.material.textfield.TextInputLayout;

import java.text.SimpleDateFormat;
import java.util.Calendar;
import java.util.Locale;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class RegisterActivity extends AppCompatActivity {

    private TextInputEditText etUsername, etEmail, etPassword, etPassword2, etPhone, etFirstName, etLastName, etBirthDate;
    private TextInputLayout usernameLayout, emailLayout, passwordLayout, passwordConfirmLayout, phoneLayout, firstNameLayout, lastNameLayout, birthDateLayout;
    private Button btnRegister;
    private ApiService apiService;
    private Calendar calendar;
    private SimpleDateFormat dateFormat;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_register);

        // Инициализируем API
        ApiClient.init(this);
        apiService = ApiClient.getApiService();

        // Инициализируем календарь и формат даты
        calendar = Calendar.getInstance();
        dateFormat = new SimpleDateFormat("yyyy-MM-dd", Locale.getDefault());

        initViews();
        setupListeners();
        setupRealTimeValidation();
        setupDatePicker();
    }

    private void initViews() {
        // TextInputLayout
        usernameLayout = findViewById(R.id.usernameLayout);
        emailLayout = findViewById(R.id.emailLayout);
        passwordLayout = findViewById(R.id.passwordLayout);
        passwordConfirmLayout = findViewById(R.id.passwordConfirmLayout);
        phoneLayout = findViewById(R.id.phoneLayout);
        firstNameLayout = findViewById(R.id.firstNameLayout);
        lastNameLayout = findViewById(R.id.lastNameLayout);
        birthDateLayout = findViewById(R.id.birthDateLayout);

        // TextInputEditText
        etUsername = findViewById(R.id.etUsername);
        etEmail = findViewById(R.id.etEmail);
        etPassword = findViewById(R.id.etPassword);
        etPassword2 = findViewById(R.id.etPassword2);
        etPhone = findViewById(R.id.etPhone);
        etFirstName = findViewById(R.id.etFirstName);
        etLastName = findViewById(R.id.etLastName);
        etBirthDate = findViewById(R.id.etBirthDate);

        // Кнопка
        btnRegister = findViewById(R.id.btnRegister);

        // Ссылка на вход
        TextView tvLoginLink = findViewById(R.id.tvLoginLink);
        tvLoginLink.setOnClickListener(v -> {
            startActivity(new Intent(RegisterActivity.this, LoginActivity.class));
            finish();
            overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
        });
    }

    private void setupListeners() {
        btnRegister.setOnClickListener(v -> {
            if (validateForm()) {
                registerUser();
            }
        });
    }

    private void setupDatePicker() {
        etBirthDate.setOnClickListener(v -> {
            int year = calendar.get(Calendar.YEAR);
            int month = calendar.get(Calendar.MONTH);
            int day = calendar.get(Calendar.DAY_OF_MONTH);

            DatePickerDialog datePickerDialog = new DatePickerDialog(
                    RegisterActivity.this,
                    (view, selectedYear, selectedMonth, selectedDay) -> {
                        calendar.set(selectedYear, selectedMonth, selectedDay);
                        etBirthDate.setText(String.format(Locale.getDefault(),
                                "%02d.%02d.%d", selectedDay, selectedMonth + 1, selectedYear));
                        birthDateLayout.setError(null);
                    },
                    year - 18, // По умолчанию 18 лет назад (для совершеннолетних)
                    month,
                    day
            );

            // Устанавливаем максимальную дату (сегодня)
            datePickerDialog.getDatePicker().setMaxDate(System.currentTimeMillis());

            // Устанавливаем минимальную дату (например, 100 лет назад)
            Calendar minDate = Calendar.getInstance();
            minDate.add(Calendar.YEAR, -100);
            datePickerDialog.getDatePicker().setMinDate(minDate.getTimeInMillis());

            datePickerDialog.show();
        });
    }

    private void setupRealTimeValidation() {
        // Валидация паролей в реальном времени
        etPassword.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {}

            @Override
            public void onTextChanged(CharSequence s, int start, int before, int count) {}

            @Override
            public void afterTextChanged(Editable s) {
                String password = s.toString();
                String confirmPassword = etPassword2.getText().toString();

                if (password.length() < 6) {
                    passwordLayout.setError("Пароль должен быть не менее 6 символов");
                } else {
                    passwordLayout.setError(null);
                }

                // Проверка совпадения паролей
                if (!confirmPassword.isEmpty() && !password.equals(confirmPassword)) {
                    passwordConfirmLayout.setError("Пароли не совпадают");
                } else if (!confirmPassword.isEmpty()) {
                    passwordConfirmLayout.setError(null);
                }
            }
        });

        etPassword2.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {}

            @Override
            public void onTextChanged(CharSequence s, int start, int before, int count) {}

            @Override
            public void afterTextChanged(Editable s) {
                String password = etPassword.getText().toString();
                String confirmPassword = s.toString();

                if (!confirmPassword.isEmpty() && !password.equals(confirmPassword)) {
                    passwordConfirmLayout.setError("Пароли не совпадают");
                } else {
                    passwordConfirmLayout.setError(null);
                }
            }
        });

        // Валидация email в реальном времени
        etEmail.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {}

            @Override
            public void onTextChanged(CharSequence s, int start, int before, int count) {}

            @Override
            public void afterTextChanged(Editable s) {
                String email = s.toString();
                if (!email.isEmpty() && !android.util.Patterns.EMAIL_ADDRESS.matcher(email).matches()) {
                    emailLayout.setError("Неверный формат email");
                } else {
                    emailLayout.setError(null);
                }
            }
        });
    }

    private boolean validateForm() {
        boolean isValid = true;

        // Сбрасываем ошибки
        usernameLayout.setError(null);
        emailLayout.setError(null);
        passwordLayout.setError(null);
        passwordConfirmLayout.setError(null);
        phoneLayout.setError(null);
        firstNameLayout.setError(null);
        lastNameLayout.setError(null);
        birthDateLayout.setError(null);

        String username = etUsername.getText().toString().trim();
        String email = etEmail.getText().toString().trim();
        String password = etPassword.getText().toString().trim();
        String password2 = etPassword2.getText().toString().trim();
        String phone = etPhone.getText().toString().trim();
        String firstName = etFirstName.getText().toString().trim();
        String lastName = etLastName.getText().toString().trim();
        String birthDate = etBirthDate.getText().toString().trim();

        // Проверка имени пользователя
        if (username.isEmpty()) {
            usernameLayout.setError("Введите имя пользователя");
            isValid = false;
        } else if (username.length() < 3) {
            usernameLayout.setError("Имя должно быть не менее 3 символов");
            isValid = false;
        } else if (ProfanityValidator.containsProfanity(username)) {
            usernameLayout.setError(ProfanityValidator.DEFAULT_ERROR_MESSAGE);
            isValid = false;
        }

        // Проверка email
        if (email.isEmpty()) {
            emailLayout.setError("Введите email");
            isValid = false;
        } else if (!android.util.Patterns.EMAIL_ADDRESS.matcher(email).matches()) {
            emailLayout.setError("Неверный формат email");
            isValid = false;
        }

        // Проверка пароля
        if (password.isEmpty()) {
            passwordLayout.setError("Введите пароль");
            isValid = false;
        } else if (password.length() < 6) {
            passwordLayout.setError("Пароль должен быть не менее 6 символов");
            isValid = false;
        }

        // Проверка подтверждения пароля
        if (password2.isEmpty()) {
            passwordConfirmLayout.setError("Подтвердите пароль");
            isValid = false;
        } else if (!password.equals(password2)) {
            passwordConfirmLayout.setError("Пароли не совпадают");
            isValid = false;
        }

        // Проверка имени (ОБЯЗАТЕЛЬНО)
        if (firstName.isEmpty()) {
            firstNameLayout.setError("Введите имя");
            isValid = false;
        } else if (ProfanityValidator.containsProfanity(firstName)) {
            firstNameLayout.setError(ProfanityValidator.DEFAULT_ERROR_MESSAGE);
            isValid = false;
        }

        // Проверка фамилии (ОБЯЗАТЕЛЬНО)
        if (lastName.isEmpty()) {
            lastNameLayout.setError("Введите фамилию");
            isValid = false;
        } else if (ProfanityValidator.containsProfanity(lastName)) {
            lastNameLayout.setError(ProfanityValidator.DEFAULT_ERROR_MESSAGE);
            isValid = false;
        }

        // Проверка даты рождения (ОБЯЗАТЕЛЬНО)
        if (birthDate.isEmpty()) {
            birthDateLayout.setError("Введите дату рождения");
            isValid = false;
        }

        // Проверка телефона
        if (!phone.isEmpty() && phone.length() < 10) {
            phoneLayout.setError("Неверный формат телефона");
            isValid = false;
        }

        return isValid;
    }

    private void registerUser() {
        // Показываем состояние загрузки
        btnRegister.setEnabled(false);
        btnRegister.setText("Регистрация...");

        // Собираем данные
        String username = etUsername.getText().toString().trim();
        String email = etEmail.getText().toString().trim();
        String password = etPassword.getText().toString().trim();
        String password2 = etPassword2.getText().toString().trim();
        String phone = etPhone.getText().toString().trim();
        String firstName = etFirstName.getText().toString().trim();
        String lastName = etLastName.getText().toString().trim();
        String birthDate = etBirthDate.getText().toString().trim();

        // Преобразуем дату в формат yyyy-MM-dd
        String formattedBirthDate = null;
        if (!birthDate.isEmpty()) {
            try {
                // Преобразуем из ДД.ММ.ГГГГ в yyyy-MM-dd
                String[] parts = birthDate.split("\\.");
                if (parts.length == 3) {
                    formattedBirthDate = String.format(Locale.getDefault(),
                            "%s-%s-%s", parts[2], parts[1], parts[0]);
                }
            } catch (Exception e) {
                e.printStackTrace();
            }
        }

        // Создаем запрос
        RegisterRequest registerRequest = new RegisterRequest();
        registerRequest.setEmail(email);
        registerRequest.setUsername(username);
        registerRequest.setPhone(phone);
        registerRequest.setPassword(password);
        registerRequest.setPassword2(password2);
        registerRequest.setFirstName(firstName);
        registerRequest.setLastName(lastName);
        registerRequest.setBirthDate(formattedBirthDate); // В формате yyyy-MM-dd
        registerRequest.setResume(""); // Можно оставить пустым

        // Отправляем запрос
        Call<TokenResponse> call = apiService.register(registerRequest);
        call.enqueue(new Callback<TokenResponse>() {
            @Override
            public void onResponse(Call<TokenResponse> call, Response<TokenResponse> response) {
                // Возвращаем кнопку в исходное состояние
                btnRegister.setEnabled(true);
                btnRegister.setText("Зарегистрироваться");

                if (response.isSuccessful() && response.body() != null) {
                    TokenResponse tokenResponse = response.body();

                    // Важно: некоторые бэкенды при регистрации НЕ возвращают JWT.
                    // В этом случае пользователь создан, но нужно просто перейти на логин.
                    if (tokenResponse.getAccessToken() != null && !tokenResponse.getAccessToken().isEmpty()) {
                        ApiClient.saveTokens(
                                tokenResponse.getAccessToken(),
                                tokenResponse.getRefreshToken(),
                                tokenResponse.getUserId(),
                                tokenResponse.getUserType()
                        );
                    } else {
                        android.util.Log.w("Register", "Registration OK, but access token is null/empty. Redirecting to Login.");
                    }

                    // Успешная регистрация
                    showSuccessMessage("Регистрация успешна! " + tokenResponse.getUsername());

                    // Задержка перед переходом
                    new android.os.Handler().postDelayed(() -> {
                        startActivity(new Intent(RegisterActivity.this, LoginActivity.class));
                        finish();
                        overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
                    }, 1000);

                } else {
                    // Обработка ошибок
                    handleRegistrationError(response);
                }
            }

            @Override
            public void onFailure(Call<TokenResponse> call, Throwable t) {
                // Возвращаем кнопку в исходное состояние
                btnRegister.setEnabled(true);
                btnRegister.setText("Зарегистрироваться");

                // Показываем ошибку сети
                Toast.makeText(RegisterActivity.this,
                        "Ошибка сети: " + t.getMessage(),
                        Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void handleRegistrationError(Response<TokenResponse> response) {
        if (response.errorBody() != null) {
            try {
                String errorBody = response.errorBody().string();
                // Попробуем распарсить JSON с ошибками
                // Здесь можно добавить парсинг JSON, если сервер возвращает детали
                Toast.makeText(this, "Ошибка регистрации: " + errorBody, Toast.LENGTH_LONG).show();

                // Логируем для отладки
                System.out.println("Registration error: " + errorBody);
            } catch (Exception e) {
                e.printStackTrace();
                Toast.makeText(this, "Ошибка: " + response.code(), Toast.LENGTH_SHORT).show();
            }
        } else {
            switch (response.code()) {
                case 400:
                    Toast.makeText(this, "Некорректные данные. Проверьте все поля.", Toast.LENGTH_LONG).show();
                    break;
                case 409:
                    emailLayout.setError("Пользователь с таким email уже существует");
                    Toast.makeText(this, "Пользователь с таким email уже зарегистрирован", Toast.LENGTH_LONG).show();
                    break;
                case 500:
                    Toast.makeText(this, "Ошибка сервера. Попробуйте позже.", Toast.LENGTH_LONG).show();
                    break;
                default:
                    Toast.makeText(this,
                            "Ошибка регистрации: " + response.code(),
                            Toast.LENGTH_SHORT).show();
            }
        }
    }

    private void showSuccessMessage(String message) {
        Toast.makeText(this, message, Toast.LENGTH_LONG).show();
    }

    @Override
    public void onBackPressed() {
        super.onBackPressed();
        overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
    }
}
