# Patrol — 구역 내 좌우 왕복 순찰 방향 결정 (A map_navigator._update_direction 재현)
import pytest
from core.navigation.patrol import Patrol, PatrolZone


def test_walks_right_then_flips_at_right_edge():
    z = PatrolZone(left_x=10, right_x=100)
    p = Patrol(z, start_dir="right", margin=0)
    assert p.next_direction(50) == "right"      # 중간 → 계속 오른쪽
    assert p.next_direction(100) == "left"      # 오른쪽 경계 → 왼쪽 전환


def test_flips_at_left_edge():
    z = PatrolZone(left_x=10, right_x=100)
    p = Patrol(z, start_dir="left", margin=0)
    assert p.next_direction(10) == "right"      # 왼쪽 경계 → 오른쪽 전환


def test_keeps_direction_inside_zone():
    z = PatrolZone(left_x=10, right_x=100)
    p = Patrol(z, start_dir="right", margin=0)
    p.next_direction(50)
    assert p.next_direction(60) == "right"      # 구역 안 → 방향 유지


def test_random_margin_flips_before_exact_edge():
    """랜덤 마진: 경계보다 margin 안쪽에서 전환 (벽에 딱 붙지 않음=사람같음)."""
    z = PatrolZone(left_x=10, right_x=100)
    p = Patrol(z, start_dir="right", margin=15, rng_seed=1)
    # 우측 목표는 (100-margin ~ 100) 사이 랜덤 → 85~100. 90에서 전환될 수 있음
    flipped = False
    for x in range(50, 101):
        if p.next_direction(x) == "left":
            flipped = True
            assert x <= 100                      # 경계 이내에서 전환
            break
    assert flipped


def test_target_x_for_block():
    """순찰 목표 X 반환 — BlockRunner move 블록에 넣을 좌표."""
    z = PatrolZone(left_x=10, right_x=100)
    p = Patrol(z, start_dir="right", margin=0)
    assert p.target_x() == 100      # 오른쪽 향하면 우측 경계가 목표
    p.next_direction(100)           # 전환
    assert p.target_x() == 10       # 왼쪽 향하면 좌측 경계
