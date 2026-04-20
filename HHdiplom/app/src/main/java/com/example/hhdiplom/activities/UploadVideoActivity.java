package com.example.hhdiplom.activities;

import android.Manifest;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.MediaStore;
import android.util.Log;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.EditText;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.work.BackoffPolicy;
import androidx.work.Constraints;
import androidx.work.Data;
import androidx.work.ExistingWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.OneTimeWorkRequest;
import androidx.work.WorkInfo;
import androidx.work.WorkManager;

import com.example.hhdiplom.R;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.models.Vacancy;
import com.example.hhdiplom.models.VacancyResponse;
import com.example.hhdiplom.utils.ProfanityValidator;
import com.example.hhdiplom.workers.VideoUploadWorker;
import com.google.android.exoplayer2.ExoPlayer;
import com.google.android.exoplayer2.MediaItem;
import com.google.android.exoplayer2.Player;
import com.google.android.exoplayer2.ui.PlayerView;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class UploadVideoActivity extends AppCompatActivity {

    private static final String TAG = "CM_UPLOAD";

    private enum PendingAction { NONE, PICK, CAPTURE }
    private PendingAction pendingAction = PendingAction.NONE;

    private Uri pickedUri;

    // выбранная вакансия
    private int vacancyId = 0;
    private String vacancyTitle = "";
    private String vacancyCity = "";

    // UI
    private TextView tvChosenVacancy;
    private Spinner spinnerVacancies;
    private LinearLayout spinnerBlock;

    private EditText etDesc;
    private ProgressBar progress;

    // preview
    private PlayerView previewPlayerView;
    private ExoPlayer previewPlayer;
    private TextView tvPreviewHint;
    private ImageButton btnClearVideo;

    // fallback data (если activity открыли без vacancy_id)
    private final List<Vacancy> companyVacancies = new ArrayList<>();
    private ArrayAdapter<String> vacancyTitlesAdapter;

    // WorkManager
    private UUID currentWorkId;
    private boolean uploadInProgress = false;

    // ===== Capture launcher =====
    private final ActivityResultLauncher<Intent> captureLauncher =
            registerForActivityResult(new ActivityResultContracts.StartActivityForResult(), res -> {
                if (res.getResultCode() == RESULT_OK && res.getData() != null) {
                    Uri uri = res.getData().getData();
                    if (uri != null) {
                        pickedUri = uri;
                        Toast.makeText(this, "Видео снято", Toast.LENGTH_SHORT).show();
                        showPreview(pickedUri);
                    }
                }
            });

    // ===== Pick launcher =====
    private final ActivityResultLauncher<String> pickLauncher =
            registerForActivityResult(new ActivityResultContracts.GetContent(), uri -> {
                if (uri != null) {
                    pickedUri = uri;
                    Toast.makeText(this, "Видео выбрано", Toast.LENGTH_SHORT).show();
                    showPreview(pickedUri);
                }
            });

    private final ActivityResultLauncher<String[]> permissionLauncher =
            registerForActivityResult(new ActivityResultContracts.RequestMultiplePermissions(), result -> {
                boolean allGranted = true;
                for (Boolean granted : result.values()) {
                    if (granted == null || !granted) {
                        allGranted = false;
                        break;
                    }
                }

                if (!allGranted) {
                    Toast.makeText(this, "Нужны разрешения для камеры/видео", Toast.LENGTH_SHORT).show();
                    pendingAction = PendingAction.NONE;
                    return;
                }

                if (pendingAction == PendingAction.PICK) {
                    pendingAction = PendingAction.NONE;
                    pickLauncher.launch("video/*");
                } else if (pendingAction == PendingAction.CAPTURE) {
                    pendingAction = PendingAction.NONE;
                    Intent i = new Intent(MediaStore.ACTION_VIDEO_CAPTURE);
                    i.putExtra(MediaStore.EXTRA_DURATION_LIMIT, 30);
                    i.putExtra(MediaStore.EXTRA_VIDEO_QUALITY, 1);
                    captureLauncher.launch(i);
                } else {
                    pendingAction = PendingAction.NONE;
                }
            });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_upload_video);

        // init prefs for tokens (важно для Worker/ApiClient)
        ApiClient.init(getApplicationContext());

        // ==== get extras from fragment ====
        vacancyId = getIntent().getIntExtra("vacancy_id", 0);
        vacancyTitle = getIntent().getStringExtra("vacancy_title");
        vacancyCity = getIntent().getStringExtra("vacancy_city");

        if (vacancyTitle == null) vacancyTitle = "";
        if (vacancyCity == null) vacancyCity = "";

        // ==== bind views ====
        tvChosenVacancy = findViewById(R.id.tvChosenVacancy);
        spinnerVacancies = findViewById(R.id.spinnerVacancies);
        spinnerBlock = findViewById(R.id.spinnerBlock);

        etDesc = findViewById(R.id.etUploadDesc);
        progress = findViewById(R.id.progressUpload);

        previewPlayerView = findViewById(R.id.previewPlayerView);
        tvPreviewHint = findViewById(R.id.tvPreviewHint);
        btnClearVideo = findViewById(R.id.btnClearVideo);

        findViewById(R.id.btnBackUpload).setOnClickListener(v -> finish());
        findViewById(R.id.btnPickVideo).setOnClickListener(v -> pickVideo());
        findViewById(R.id.btnCaptureVideo).setOnClickListener(v -> captureVideo());
        findViewById(R.id.btnUploadVideo).setOnClickListener(v -> enqueueUpload());
        btnClearVideo.setOnClickListener(v -> clearPickedVideo());

        // ==== setup preview player ====
        previewPlayer = new ExoPlayer.Builder(this).build();
        previewPlayer.setRepeatMode(Player.REPEAT_MODE_ALL);
        previewPlayerView.setPlayer(previewPlayer);

        // ==== if vacancy is passed -> hide spinner and show chosen vacancy ====
        if (vacancyId > 0) {
            spinnerBlock.setVisibility(View.GONE);
            tvChosenVacancy.setVisibility(View.VISIBLE);

            String text = vacancyTitle.isEmpty()
                    ? ("Вакансия #" + vacancyId)
                    : (vacancyTitle + (vacancyCity.isEmpty() ? "" : (" • " + vacancyCity)));
            tvChosenVacancy.setText(text);
        } else {
            // fallback mode: allow selecting vacancy in spinner
            tvChosenVacancy.setVisibility(View.GONE);
            spinnerBlock.setVisibility(View.VISIBLE);
            setupSpinner();
            loadCompanyVacancies();
        }

        // initial preview state
        setPreviewVisible(false);
        progress.setVisibility(View.GONE);
    }

    private void setupSpinner() {
        vacancyTitlesAdapter = new ArrayAdapter<>(
                this,
                android.R.layout.simple_spinner_dropdown_item,
                new ArrayList<>()
        );
        spinnerVacancies.setAdapter(vacancyTitlesAdapter);
        spinnerVacancies.setEnabled(false);

        spinnerVacancies.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(android.widget.AdapterView<?> parent, View view, int position, long id) {
                if (position >= 0 && position < companyVacancies.size()) {
                    Vacancy v = companyVacancies.get(position);
                    vacancyId = v.getId();
                    vacancyTitle = v.getPosition();
                    vacancyCity = v.getCity();

                    tvChosenVacancy.setVisibility(View.VISIBLE);
                    tvChosenVacancy.setText(vacancyTitle + " • " + vacancyCity);
                }
            }

            @Override
            public void onNothingSelected(android.widget.AdapterView<?> parent) {
                vacancyId = 0;
            }
        });
    }

    // ===== Vacancies (fallback) =====
    private void loadCompanyVacancies() {
        progress.setVisibility(View.VISIBLE);
        spinnerVacancies.setEnabled(false);
        companyVacancies.clear();
        vacancyTitlesAdapter.clear();
        vacancyTitlesAdapter.notifyDataSetChanged();

        fetchCmVacancies(1);
    }

    private void fetchCmVacancies(int page) {
        Log.d(TAG, "GET cm vacancies page=" + page);

        ApiClient.getApiService().getContentManagerVacancies(page)
                .enqueue(new Callback<VacancyResponse>() {
                    @Override
                    public void onResponse(@NonNull Call<VacancyResponse> call,
                                           @NonNull Response<VacancyResponse> response) {

                        Log.d(TAG, "cm vacancies response code=" + response.code());

                        if (!response.isSuccessful()) {
                            progress.setVisibility(View.GONE);
                            toast("Ошибка загрузки вакансий: " + response.code());
                            return;
                        }

                        VacancyResponse body = response.body();
                        if (body == null || body.getResults() == null) {
                            progress.setVisibility(View.GONE);
                            toast("Пустой ответ вакансий");
                            return;
                        }

                        companyVacancies.addAll(body.getResults());

                        boolean hasNext = body.getNext() != null;
                        if (hasNext) {
                            fetchCmVacancies(page + 1);
                            return;
                        }

                        progress.setVisibility(View.GONE);

                        if (companyVacancies.isEmpty()) {
                            toast("У компании нет вакансий");
                            return;
                        }

                        List<String> titles = new ArrayList<>();
                        for (Vacancy v : companyVacancies) {
                            titles.add(v.getPosition() + " • " + v.getCity());
                        }

                        vacancyTitlesAdapter.clear();
                        vacancyTitlesAdapter.addAll(titles);
                        vacancyTitlesAdapter.notifyDataSetChanged();
                        spinnerVacancies.setEnabled(true);
                    }

                    @Override
                    public void onFailure(@NonNull Call<VacancyResponse> call, @NonNull Throwable t) {
                        progress.setVisibility(View.GONE);
                        Log.e(TAG, "cm vacancies failure: " + t.getMessage(), t);
                        toast("Сетевая ошибка (CM вакансии): " + t.getMessage());
                    }
                });
    }

    // ===== Permissions + Pick/Capture =====
    private void requestPermissionsIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissionLauncher.launch(new String[]{Manifest.permission.CAMERA, Manifest.permission.READ_MEDIA_VIDEO});
        } else {
            permissionLauncher.launch(new String[]{Manifest.permission.CAMERA, Manifest.permission.READ_EXTERNAL_STORAGE});
        }
    }

    private void pickVideo() {
        if (uploadInProgress) { toast("Идёт загрузка…"); return; }
        pendingAction = PendingAction.PICK;
        requestPermissionsIfNeeded();
    }

    private void captureVideo() {
        if (uploadInProgress) { toast("Идёт загрузка…"); return; }
        pendingAction = PendingAction.CAPTURE;
        requestPermissionsIfNeeded();
    }

    // ===== Preview =====
    private void showPreview(Uri uri) {
        if (uri == null) return;
        setPreviewVisible(true);

        try {
            previewPlayer.stop();
            previewPlayer.clearMediaItems();
            previewPlayer.setMediaItem(MediaItem.fromUri(uri));
            previewPlayer.prepare();
            previewPlayer.play();
        } catch (Exception e) {
            Log.e(TAG, "preview error: " + e.getMessage(), e);
        }
    }

    private void clearPickedVideo() {
        if (uploadInProgress) { toast("Нельзя очищать во время загрузки"); return; }

        pickedUri = null;
        try {
            previewPlayer.stop();
            previewPlayer.clearMediaItems();
        } catch (Exception ignored) {}
        setPreviewVisible(false);
    }

    private void setPreviewVisible(boolean visible) {
        previewPlayerView.setVisibility(visible ? View.VISIBLE : View.GONE);
        btnClearVideo.setVisibility(visible ? View.VISIBLE : View.GONE);
        tvPreviewHint.setVisibility(visible ? View.GONE : View.VISIBLE);
    }

    // ===== Upload via WorkManager (вынесено из Activity) =====
    private void enqueueUpload() {
        try { if (previewPlayer != null) previewPlayer.pause(); } catch (Exception ignored) {}

        if (uploadInProgress) {
            toast("Загрузка уже идёт…");
            return;
        }
        if (vacancyId <= 0) { toast("Не выбрана вакансия"); return; }
        if (pickedUri == null) { toast("Выберите или снимите видео"); return; }

        String description = etDesc.getText() != null ? etDesc.getText().toString().trim() : "";
        if (!description.isEmpty() && ProfanityValidator.containsProfanity(description)) {
            toast(ProfanityValidator.DEFAULT_ERROR_MESSAGE);
            return;
        }

        uploadInProgress = true;
        progress.setVisibility(View.VISIBLE);
        setUploadButtonsEnabled(false);

        Data input = new Data.Builder()
                .putString(VideoUploadWorker.KEY_URI, pickedUri.toString())
                .putInt(VideoUploadWorker.KEY_VACANCY_ID, vacancyId)
                .putString(VideoUploadWorker.KEY_DESC, description)
                .build();

        Constraints constraints = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();

        OneTimeWorkRequest req = new OneTimeWorkRequest.Builder(VideoUploadWorker.class)
                .setInputData(input)
                .setConstraints(constraints)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 10, TimeUnit.SECONDS)
                .build();

        currentWorkId = req.getId();

        WorkManager.getInstance(getApplicationContext())
                .enqueueUniqueWork("video_upload", ExistingWorkPolicy.REPLACE, req);

        observeUpload(req.getId());

        toast("Загрузка началась (в фоне) ✅");
        // можно сразу закрыть экран:
        // finish();
    }

    private void observeUpload(UUID id) {
        WorkManager.getInstance(getApplicationContext())
                .getWorkInfoByIdLiveData(id)
                .observe(this, info -> {
                    if (info == null) return;

                    int p = info.getProgress().getInt(VideoUploadWorker.KEY_PROGRESS, 0);
                    Log.d(TAG, "worker progress=" + p + "% state=" + info.getState());

                    if (info.getState() == WorkInfo.State.SUCCEEDED) {
                        finishUploadUI();
                        toast("Видео загружено ✅");
                        Intent result = new Intent();
                        result.putExtra("video_uploaded", true);
                        result.putExtra("vacancy_id", vacancyId);
                        setResult(RESULT_OK, result);
                        finish();
                    } else if (info.getState() == WorkInfo.State.FAILED) {
                        finishUploadUI();
                        String err = info.getOutputData().getString(VideoUploadWorker.KEY_ERROR);
                        toast("Ошибка: " + (err == null ? "unknown" : err));
                    } else if (info.getState() == WorkInfo.State.CANCELLED) {
                        finishUploadUI();
                        toast("Загрузка отменена");
                    } else {
                        // RUNNING/ENQUEUED - оставляем UI как есть
                    }
                });
    }

    private void finishUploadUI() {
        uploadInProgress = false;
        progress.setVisibility(View.GONE);
        setUploadButtonsEnabled(true);
    }

    private void setUploadButtonsEnabled(boolean enabled) {
        View b1 = findViewById(R.id.btnPickVideo);
        View b2 = findViewById(R.id.btnCaptureVideo);
        View b3 = findViewById(R.id.btnUploadVideo);
        if (b1 != null) b1.setEnabled(enabled);
        if (b2 != null) b2.setEnabled(enabled);
        if (b3 != null) b3.setEnabled(enabled);
        if (btnClearVideo != null) btnClearVideo.setEnabled(enabled);
    }

    private void toast(String s) {
        Toast.makeText(this, s, Toast.LENGTH_SHORT).show();
    }

    @Override
    protected void onStop() {
        super.onStop();
        if (previewPlayer != null) previewPlayer.pause();
    }

    @Override
    protected void onDestroy() {
        Log.w(TAG, "onDestroy uploadInProgress=" + uploadInProgress + " workId=" + currentWorkId);
        // ВАЖНО: НЕ отменяем work здесь. Иначе снова будет "на больших видео всё ломается".
        // Если нужно добавить кнопку "Отменить" — отменяй WorkManager.cancelWorkById(currentWorkId)
        if (previewPlayer != null) {
            try {
                previewPlayer.release();
            } catch (Exception ignored) {}
            previewPlayer = null;
        }
        super.onDestroy();
    }
}
