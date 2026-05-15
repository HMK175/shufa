"""DDPG 轨迹优化模块。

将骨架提取 + B样条平滑后的笔画轨迹作为初始解，
用 DDPG 对每个轨迹点做局部微调，最大化轨迹渲染与原图的相似度。

论文对应：第 X 章 "基于深度强化学习的轨迹局部优化"
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import deque
import random

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

# ============================================================
# 网络定义
# ============================================================

class Actor(nn.Module):
    """策略网络：状态 → 位移动作 (Δy, Δx)。"""
    def __init__(self, state_dim: int, action_dim: int = 2, max_action: float = 3.0):
        super().__init__()
        self.max_action = max_action
        self.net = nn.Sequential(
            nn.Linear(state_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, action_dim),
            nn.Tanh(),
        )

    def forward(self, state):
        return self.max_action * self.net(state)


class Critic(nn.Module):
    """价值网络：状态+动作 → Q值。"""
    def __init__(self, state_dim: int, action_dim: int = 2):
        super().__init__()
        self.fc_s = nn.Linear(state_dim, 128)
        self.fc_a = nn.Linear(action_dim, 128)
        self.fc_out = nn.Sequential(
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 1),
        )

    def forward(self, state, action):
        hs = F.relu(self.fc_s(state))
        ha = F.relu(self.fc_a(action))
        h = torch.cat([hs, ha], dim=-1)
        return self.fc_out(h)


# ============================================================
# Replay Buffer
# ============================================================

class ReplayBuffer:
    def __init__(self, capacity: int = 10000):
        self.buffer = deque(maxlen=capacity)

    def push(self, s, a, r, s_next, done):
        self.buffer.append((s, a, r, s_next, done))

    def sample(self, batch_size: int):
        batch = random.sample(self.buffer, min(batch_size, len(self.buffer)))
        states, actions, rewards, next_states, dones = zip(*batch)
        return (
            torch.FloatTensor(np.array(states)),
            torch.FloatTensor(np.array(actions)),
            torch.FloatTensor(np.array(rewards)).unsqueeze(1),
            torch.FloatTensor(np.array(next_states)),
            torch.FloatTensor(np.array(dones)).unsqueeze(1),
        )

    def __len__(self):
        return len(self.buffer)


# ============================================================
# DDPG Agent
# ============================================================

class DDPGAgent:
    def __init__(
        self,
        state_dim: int,
        action_dim: int = 2,
        max_action: float = 3.0,
        lr_actor: float = 1e-4,
        lr_critic: float = 1e-3,
        gamma: float = 0.95,
        tau: float = 0.005,
        device: str = "cpu",
    ):
        self.device = torch.device(device)
        self.max_action = max_action
        self.gamma = gamma
        self.tau = tau

        self.actor = Actor(state_dim, action_dim, max_action).to(self.device)
        self.actor_target = Actor(state_dim, action_dim, max_action).to(self.device)
        self.actor_target.load_state_dict(self.actor.state_dict())

        self.critic = Critic(state_dim, action_dim).to(self.device)
        self.critic_target = Critic(state_dim, action_dim).to(self.device)
        self.critic_target.load_state_dict(self.critic.state_dict())

        self.actor_optimizer = optim.Adam(self.actor.parameters(), lr=lr_actor)
        self.critic_optimizer = optim.Adam(self.critic.parameters(), lr=lr_critic)

        self.replay_buffer = ReplayBuffer()
        self.total_steps = 0

    def select_action(self, state: np.ndarray, add_noise: bool = True) -> np.ndarray:
        with torch.no_grad():
            state_t = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            action = self.actor(state_t).cpu().numpy().flatten()
        if add_noise:
            # Ornstein-Uhlenbeck 噪声
            noise = np.random.normal(0, self.max_action * 0.1, size=action.shape)
            action = np.clip(action + noise, -self.max_action, self.max_action)
        return action

    def update(self, batch_size: int = 64):
        if len(self.replay_buffer) < batch_size:
            return

        states, actions, rewards, next_states, dones = self.replay_buffer.sample(batch_size)
        states = states.to(self.device)
        actions = actions.to(self.device)
        rewards = rewards.to(self.device)
        next_states = next_states.to(self.device)
        dones = dones.to(self.device)

        # 更新 Critic
        with torch.no_grad():
            next_actions = self.actor_target(next_states)
            target_q = self.critic_target(next_states, next_actions)
            target_q = rewards + (1 - dones) * self.gamma * target_q

        current_q = self.critic(states, actions)
        critic_loss = F.mse_loss(current_q, target_q)

        self.critic_optimizer.zero_grad()
        critic_loss.backward()
        self.critic_optimizer.step()

        # 更新 Actor
        actor_actions = self.actor(states)
        actor_loss = -self.critic(states, actor_actions).mean()

        self.actor_optimizer.zero_grad()
        actor_loss.backward()
        self.actor_optimizer.step()

        # 软更新目标网络
        for target, source in zip(self.critic_target.parameters(), self.critic.parameters()):
            target.data.copy_(self.tau * source.data + (1 - self.tau) * target.data)
        for target, source in zip(self.actor_target.parameters(), self.actor.parameters()):
            target.data.copy_(self.tau * source.data + (1 - self.tau) * target.data)

        self.total_steps += 1


# ============================================================
# 环境：轨迹点微调
# ============================================================

class TrajectoryEnv:
    """轨迹优化环境。

    每步对一个笔画点做微调，奖励基于渲染轨迹与目标图像的相似度。
    渲染使用自适应线宽（通过距离变换估算笔画半径）。
    """

    def __init__(
        self,
        binary: np.ndarray,
        skeleton: np.ndarray,
        stroke_points: np.ndarray,
        max_action: float = 3.0,
        patch_size: int = 7,
        render_thickness: int = -1,  # -1 = auto from distance transform
    ):
        """
        Args:
            binary: (H, W) 二值图 (0/255)
            skeleton: (H, W) 骨架图 (0/255)
            stroke_points: (N, 2) 初始笔画轨迹 [y, x]
        """
        self.binary = (binary > 0).astype(np.float32)
        self.H, self.W = binary.shape
        self.max_action = max_action
        self.patch_size = patch_size

        # 初始轨迹
        self.initial_points = stroke_points.copy()
        self.points = stroke_points.copy().astype(np.float32)
        self.N = len(self.points)

        self.current_idx = 0
        self.done = False

        # 预计算距离变换
        from scipy import ndimage
        # fg→背景距离 (用于 Chamfer 度量：轨迹点离前景多远)
        self.fg_dist = ndimage.distance_transform_edt(1 - self.binary)
        # skeleton→最近骨架距离 (用于奖励贴近中心线)
        skel_binary = (skeleton > 0).astype(np.float32)
        self.skel_dist = ndimage.distance_transform_edt(1 - skel_binary)
        # 前景→边缘距离 (用于估算笔画半宽)
        half_width = ndimage.distance_transform_edt(self.binary)
        fg_mask = self.binary > 0

        # 自适应线宽
        if render_thickness < 0:
            if fg_mask.any():
                mean_hw = half_width[fg_mask].mean()
                self.render_thickness = max(3, int(2 * mean_hw))
            else:
                self.render_thickness = 3
        else:
            self.render_thickness = render_thickness

    def reset(self, stroke_points: Optional[np.ndarray] = None) -> np.ndarray:
        if stroke_points is not None:
            self.initial_points = stroke_points.copy()
            self.points = stroke_points.copy().astype(np.float32)
            self.N = len(self.points)
        else:
            self.points = self.initial_points.copy()
        self.current_idx = 0
        self.done = False
        return self._get_state()

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool]:
        """执行一步微调。

        Args:
            action: (2,) Δy, Δx 位移

        Returns:
            state, reward, done
        """
        # 应用位移
        dy, dx = action[0], action[1]
        old_pos = self.points[self.current_idx].copy()

        new_y = np.clip(old_pos[0] + dy, 0, self.H - 1)
        new_x = np.clip(old_pos[1] + dx, 0, self.W - 1)
        self.points[self.current_idx] = np.array([new_y, new_x])

        # 计算奖励
        reward = self._compute_reward(self.current_idx, old_pos)

        self.current_idx += 1
        if self.current_idx >= self.N:
            self.done = True

        return self._get_state(), reward, self.done

    def _get_state(self) -> np.ndarray:
        """构建当前点的状态向量。"""
        if self.current_idx >= self.N:
            self.current_idx = self.N - 1

        y, x = self.points[self.current_idx]
        yi, xi = int(round(y)), int(round(x))

        # 1. 归一化位置 (2)
        pos_feat = np.array([y / self.H, x / self.W], dtype=np.float32)

        # 2. 局部二值图 patch (patch_size^2)
        r = self.patch_size // 2
        patch = np.zeros((self.patch_size, self.patch_size), dtype=np.float32)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                ny, nx = yi + dy, xi + dx
                if 0 <= ny < self.H and 0 <= nx < self.W:
                    patch[dy + r, dx + r] = self.binary[ny, nx]
        patch_feat = patch.flatten()

        # 3. 到前景的距离 (1)
        if 0 <= yi < self.H and 0 <= xi < self.W:
            fg_d = self.fg_dist[yi, xi]
        else:
            fg_d = 0.0
        dist_feat = np.array([fg_d / max(self.H, self.W)], dtype=np.float32)

        # 4. 局部方向 (4): 前一点方向 + 后一点方向
        dir_feat = np.zeros(4, dtype=np.float32)
        if self.current_idx > 0:
            prev = self.points[self.current_idx - 1]
            d_prev = np.array([y, x]) - prev
            norm = np.linalg.norm(d_prev) + 1e-6
            dir_feat[:2] = d_prev / norm
        else:
            dir_feat[:2] = np.array([0.0, 0.0])

        if self.current_idx < self.N - 1:
            nxt = self.points[self.current_idx + 1]
            d_next = nxt - np.array([y, x])
            norm = np.linalg.norm(d_next) + 1e-6
            dir_feat[2:] = d_next / norm
        else:
            dir_feat[2:] = np.array([0.0, 0.0])

        # 5. 局部曲率 (1): 相邻三点的角度变化
        curv_feat = np.zeros(1, dtype=np.float32)
        if 0 < self.current_idx < self.N - 1:
            v1 = self.points[self.current_idx] - self.points[self.current_idx - 1]
            v2 = self.points[self.current_idx + 1] - self.points[self.current_idx]
            n1, n2 = np.linalg.norm(v1) + 1e-6, np.linalg.norm(v2) + 1e-6
            cos_angle = np.dot(v1 / n1, v2 / n2)
            curv_feat[0] = (1 - cos_angle) / 2  # 0=直线, 1=急弯

        return np.concatenate([pos_feat, patch_feat, dist_feat, dir_feat, curv_feat]).astype(np.float32)

    def _compute_reward(self, idx: int, old_pos: np.ndarray) -> float:
        """计算单步奖励：更靠近前景中心 + 保持平滑。"""
        y, x = self.points[idx]
        yi, xi = int(round(y)), int(round(x))
        old_yi, old_xi = int(round(old_pos[0])), int(round(old_pos[1]))

        # 奖励1：到前景的距离改进
        if 0 <= yi < self.H and 0 <= xi < self.W:
            old_fg = self.fg_dist[old_yi, old_xi] if (0 <= old_yi < self.H and 0 <= old_xi < self.W) else 20.0
            new_fg = self.fg_dist[yi, xi]
            r_foreground = (old_fg - new_fg) / self.render_thickness * 2.0
        else:
            r_foreground = -0.5

        # 奖励2：在笔画宽度范围内（距离 < 笔画半径 → 正奖励）
        if 0 <= yi < self.H and 0 <= xi < self.W:
            if self.binary[yi, xi] > 0:
                r_inside = 0.3
            else:
                fg_d = self.fg_dist[yi, xi]
                r_inside = max(-0.5, -fg_d / self.render_thickness)
        else:
            r_inside = -0.5

        # 奖励3：贴近骨架中心线
        if 0 <= yi < self.H and 0 <= xi < self.W:
            r_skeleton = -self.skel_dist[yi, xi] / self.render_thickness
        else:
            r_skeleton = -0.5

        # 奖励4：平滑性
        if idx > 0:
            dist_to_prev = np.linalg.norm(self.points[idx] - self.points[idx - 1])
            r_smooth = -max(0, dist_to_prev - 3.0) / 20.0
        else:
            r_smooth = 0.0

        # 奖励5：出界惩罚
        r_boundary = -0.5 if (yi < 0 or yi >= self.H or xi < 0 or xi >= self.W) else 0.0

        return 0.25 * r_foreground + 0.25 * r_inside + 0.2 * r_skeleton + 0.2 * r_smooth + 0.1 * r_boundary

    def get_trajectory(self) -> np.ndarray:
        return self.points.copy()

    def get_rendered_trajectory(self) -> np.ndarray:
        """将当前轨迹渲染为二值图（使用自适应线宽）。"""
        import cv2
        canvas = np.zeros((self.H, self.W), dtype=np.uint8)
        pts = self.points.astype(np.int32).reshape(-1, 1, 2)
        pts_xy = pts[..., ::-1].astype(np.int32)  # y,x → x,y
        cv2.polylines(canvas, [pts_xy], False, 255, self.render_thickness)
        return canvas

    def compute_iou(self) -> float:
        """当前轨迹渲染与原图的 IoU。"""
        rendered = (self.get_rendered_trajectory() > 0).astype(np.float32)
        target = self.binary
        intersection = np.logical_and(rendered, target).sum()
        union = np.logical_or(rendered, target).sum()
        return intersection / union if union > 0 else 0.0

    def compute_chamfer(self) -> float:
        """计算轨迹点到前景的 Chamfer 距离（越小越好）。"""
        pts = self.points
        chamfer = 0.0
        for y, x in pts:
            yi, xi = int(round(y)), int(round(x))
            if 0 <= yi < self.H and 0 <= xi < self.W:
                chamfer += self.fg_dist[yi, xi]
            else:
                chamfer += 20.0
        return chamfer / len(pts) if len(pts) > 0 else 0.0

    @property
    def state_dim(self) -> int:
        return self._get_state().shape[0]


# ============================================================
# 训练与优化接口
# ============================================================

def add_noise_to_stroke(stroke: np.ndarray, noise_std: float = 4.0) -> np.ndarray:
    """给笔画轨迹添加高斯噪声（模拟不完美初始化）。"""
    noisy = stroke.copy().astype(np.float32)
    noise = np.random.randn(*noisy.shape) * noise_std
    # 首尾点不加噪（锚定端点）
    noise[0] *= 0.1
    noise[-1] *= 0.1
    return np.clip(noisy + noise, 0, None)


def _clip_displacement(traj: np.ndarray, ref: np.ndarray, max_disp: float = 4.0) -> np.ndarray:
    """将 traj 每个点相对于 ref 的偏移限制在 max_disp 像素内。"""
    clipped = traj.copy()
    for i in range(len(traj)):
        delta = clipped[i] - ref[i]
        dist = np.linalg.norm(delta)
        if dist > max_disp:
            clipped[i] = ref[i] + delta / dist * max_disp
    return clipped


def optimize_trajectory_rl(
    binary: np.ndarray,
    skeleton: np.ndarray,
    strokes: List[np.ndarray],
    episodes_per_stroke: int = 300,
    noise_std: float = 2.0,
    device: str = "cpu",
    verbose: bool = True,
) -> Tuple[List[np.ndarray], List[np.ndarray], dict]:
    """用 DDPG 逐笔画优化轨迹。

    Args:
        binary: (H, W) 二值图
        skeleton: (H, W) 骨架图
        strokes: 笔画列表，每个 (N_i, 2)
        episodes_per_stroke: 每笔画的训练轮数
        noise_std: 加噪标准差（模拟初始化误差）
        device: "cpu" 或 "cuda"
        verbose: 是否打印进度

    Returns:
        (优化后的笔画, 加噪后的笔画, 统计信息)
    """
    noisy_strokes = []
    optimized_strokes = []
    stats = {"init_iou": [], "noisy_iou": [], "final_iou": [],
             "init_chamfer": [], "noisy_chamfer": [], "final_chamfer": []}

    for si, stroke in enumerate(strokes):
        if len(stroke) < 4:
            noisy_strokes.append(stroke.copy())
            optimized_strokes.append(stroke.copy())
            continue

        # 计算初始指标（始终计算，用于回退判断）
        init_env = TrajectoryEnv(binary, skeleton, stroke)
        init_iou = init_env.compute_iou()
        init_chamfer = init_env.compute_chamfer()

        # 加噪
        noisy = add_noise_to_stroke(stroke, noise_std)
        noisy_strokes.append(noisy)

        # DDPG 训练
        env = TrajectoryEnv(binary, skeleton, noisy)
        state_dim = env.state_dim
        agent = DDPGAgent(state_dim=state_dim, device=device)

        noisy_iou = env.compute_iou()
        noisy_chamfer = env.compute_chamfer()

        best_iou = noisy_iou
        best_traj = noisy.copy()
        best_chamfer = noisy_chamfer

        for ep in range(episodes_per_stroke):
            state = env.reset()
            done = False

            while not done:
                action = agent.select_action(state, add_noise=(ep < episodes_per_stroke * 0.7))
                next_state, reward, done = env.step(action)
                agent.replay_buffer.push(state, action, reward, next_state, float(done))
                agent.update(batch_size=64)
                state = next_state

            # 评估
            eval_state = env.reset()
            done = False
            while not done:
                action = agent.select_action(eval_state, add_noise=False)
                next_state, _, done = env.step(action)
                eval_state = next_state

            current_iou = env.compute_iou()
            if current_iou > best_iou:
                best_iou = current_iou
                best_traj = env.get_trajectory().copy()
                best_chamfer = env.compute_chamfer()

        # 回退保护：RL 结果不能比初始平滑轨迹差
        if best_iou < init_iou or best_chamfer > init_chamfer * 1.1:
            if verbose:
                print(f"  Stroke {si+1}/{len(strokes)}: FALLBACK — "
                      f"RL IoU={best_iou:.3f} vs init={init_iou:.3f}, "
                      f"Chamfer={best_chamfer:.1f} vs init={init_chamfer:.1f}px")
            best_traj = stroke.copy().astype(np.float32)
            best_iou = init_iou
            best_chamfer = init_chamfer
        else:
            # 限制单点最大位移（相对原始平滑轨迹）
            best_traj = _clip_displacement(best_traj, stroke.astype(np.float32), max_disp=4.0)

        if verbose:
            print(f"  Stroke {si+1}/{len(strokes)}: "
                  f"IoU {noisy_iou:.3f}->{best_iou:.3f} "
                  f"(init={init_iou:.3f}), "
                  f"Chamfer {noisy_chamfer:.1f}->{best_chamfer:.1f}px "
                  f"(init={init_chamfer:.1f})")

        stats["init_iou"].append(init_iou)
        stats["noisy_iou"].append(noisy_iou)
        stats["final_iou"].append(best_iou)
        stats["init_chamfer"].append(init_chamfer)
        stats["noisy_chamfer"].append(noisy_chamfer)
        stats["final_chamfer"].append(best_chamfer)

        optimized_strokes.append(best_traj)

    return optimized_strokes, noisy_strokes, stats
