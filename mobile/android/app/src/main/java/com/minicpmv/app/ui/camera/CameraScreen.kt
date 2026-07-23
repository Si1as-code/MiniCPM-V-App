package com.minicpmv.app.ui.camera

import android.Manifest
import android.content.pm.PackageManager
import androidx.camera.view.PreviewView
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.ChatBubble
import androidx.compose.material.icons.filled.FlashAuto
import androidx.compose.material.icons.filled.FlashOff
import androidx.compose.material.icons.filled.FlashOn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import com.minicpmv.app.camera.CameraManager
import com.minicpmv.app.inference.InferenceResult
import com.minicpmv.app.ui.theme.PrimaryBlue
import com.minicpmv.app.ui.theme.SuccessGreen
import com.minicpmv.app.viewmodel.MainViewModel
import kotlinx.coroutines.launch

/**
 * 相机拍照页面 - 核心交互界面
 *
 * 功能:
 * - CameraX 实时预览
 * - 拍照按钮
 * - 闪光灯控制
 * - 识别结果展示
 * - 快速进入对话
 */
@Composable
fun CameraScreen(
    modifier: Modifier = Modifier,
    snackbarHostState: SnackbarHostState,
    viewModel: MainViewModel = viewModel()
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val scope = rememberCoroutineScope()

    val cameraManager = remember { CameraManager(context) }
    val previewView = remember { PreviewView(context) }

    val isInferencing by viewModel.isInferencing
    val lastResult by viewModel.lastResult

    var flashMode by remember { mutableIntStateOf(androidx.camera.core.ImageCapture.FLASH_MODE_AUTO) }
    var hasPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                    PackageManager.PERMISSION_GRANTED
        )
    }

    // 启动相机
    LaunchedEffect(hasPermission) {
        if (hasPermission) {
            try {
                cameraManager.startCamera(previewView, lifecycleOwner)
                viewModel.setCameraReady(true)
            } catch (e: Exception) {
                snackbarHostState.showSnackbar("相机启动失败: ${e.message}")
            }
        }
    }

    // 清理
    DisposableEffect(Unit) {
        onDispose {
            cameraManager.shutdown()
        }
    }

    Box(modifier = modifier.fillMaxSize()) {
        // 相机预览
        AndroidView(
            factory = { previewView },
            modifier = Modifier.fillMaxSize()
        )

        // 顶部控制栏
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
                .align(Alignment.TopCenter),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            FlashButton(
                flashMode = flashMode,
                onFlashChange = {
                    flashMode = when (flashMode) {
                        androidx.camera.core.ImageCapture.FLASH_MODE_AUTO -> androidx.camera.core.ImageCapture.FLASH_MODE_ON
                        androidx.camera.core.ImageCapture.FLASH_MODE_ON -> androidx.camera.core.ImageCapture.FLASH_MODE_OFF
                        else -> androidx.camera.core.ImageCapture.FLASH_MODE_AUTO
                    }
                    cameraManager.setFlashMode(flashMode)
                }
            )
        }

        // 底部控制区
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .align(Alignment.BottomCenter)
                .padding(bottom = 32.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // 识别结果卡片
            if (lastResult != null && !isInferencing) {
                ResultCard(
                    result = lastResult!!,
                    onChatClick = { /* TODO: 导航到对话 */ },
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
                )
            }

            // 拍照按钮
            CaptureButton(
                isLoading = isInferencing,
                onCapture = {
                    scope.launch {
                        try {
                            val bitmap = cameraManager.takePhoto()
                            viewModel.runInference(bitmap)
                        } catch (e: Exception) {
                            snackbarHostState.showSnackbar("拍照失败: ${e.message}")
                        }
                    }
                },
                modifier = Modifier.padding(top = 16.dp)
            )
        }

        // 加载指示器
        if (isInferencing) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(MaterialTheme.colorScheme.scrim.copy(alpha = 0.3f)),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = PrimaryBlue)
            }
        }
    }
}

@Composable
private fun FlashButton(flashMode: Int, onFlashChange: () -> Unit) {
    val icon = when (flashMode) {
        androidx.camera.core.ImageCapture.FLASH_MODE_ON -> Icons.Filled.FlashOn
        androidx.camera.core.ImageCapture.FLASH_MODE_OFF -> Icons.Filled.FlashOff
        else -> Icons.Filled.FlashAuto
    }
    IconButton(
        onClick = onFlashChange,
        modifier = Modifier
            .size(48.dp)
            .background(MaterialTheme.colorScheme.scrim.copy(alpha = 0.5f), CircleShape)
    ) {
        Icon(icon, contentDescription = "闪光灯", tint = MaterialTheme.colorScheme.onPrimary)
    }
}

@Composable
private fun CaptureButton(
    isLoading: Boolean,
    onCapture: () -> Unit,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .size(80.dp)
            .clip(CircleShape)
            .background(if (isLoading) MaterialTheme.colorScheme.surfaceVariant else PrimaryBlue)
            .padding(4.dp),
        contentAlignment = Alignment.Center
    ) {
        IconButton(
            onClick = onCapture,
            enabled = !isLoading,
            modifier = Modifier.fillMaxSize()
        ) {
            Icon(
                Icons.Filled.CameraAlt,
                contentDescription = "拍照",
                tint = MaterialTheme.colorScheme.onPrimary,
                modifier = Modifier.size(36.dp)
            )
        }
    }
}

@Composable
private fun ResultCard(
    result: InferenceResult,
    onChatClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.95f)
        )
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = if (result.success) "识别成功" else "识别失败",
                    style = MaterialTheme.typography.titleMedium,
                    color = if (result.success) SuccessGreen else MaterialTheme.colorScheme.error
                )
                Text(
                    text = "${result.latencyMs}ms",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = result.answer,
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 3,
                overflow = TextOverflow.Ellipsis
            )

            if (result.success) {
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    LinearProgressIndicator(
                        progress = { result.confidence },
                        modifier = Modifier.weight(1f),
                        color = if (result.confidence > 0.8f) SuccessGreen else MaterialTheme.colorScheme.primary
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "${(result.confidence * 100).toInt()}%",
                        style = MaterialTheme.typography.labelMedium
                    )
                }

                Spacer(modifier = Modifier.height(8.dp))
                TextButton(onClick = onChatClick) {
                    Icon(Icons.Filled.ChatBubble, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("继续对话")
                }
            }
        }
    }
}
